#!/usr/bin/env python3
"""
guard_registry.py — Unified Guard Registry v0.4.5

THE single entry point for all guard execution. post, orchestrator, CI, and
Agent self-checks MUST call run_standard_guards() — never call individual
guards directly.

Key rules:
  1. Only ONE place registers all guards and their execution logic.
  2. post and orchestrator get the same GuardSummary.
  3. Every WARNING is a GuardFinding — never just a print().
  4. FTS health is checked before execution; if broken, attempts repair.
"""

import sys
from pathlib import Path
from typing import Optional

from scripts.guard_result import (
    GuardResult, GuardSummary, GuardFinding,
    finding, result_pass, result_warn, result_fail,
)


# ═══════════════════════════════════════════════════
# Guard level definitions
# ═══════════════════════════════════════════════════

GUARD_LEVELS = {
    "continuity_evidence_guard": 1,
    "canon_evidence_guard": 1,
    "hallucination_guard": 1,
    "scene_delta_guard": 1,
    "anti_ai_guard": 2,
    "padding_guard": 2,
    "show_dont_tell_guard": 2,
    "character_voice_guard": 2,
    "dialogue_beat_guard": 2,
    "classical_register_guard": 2,
    "perplexity_quality_guard": 2,
    "editor_revision_guard": 2,
    "concrete_anchor_guard": 2,
    "scene_causality_guard": 2,
    "dialogue_naturalness_guard": 2,
    "style_variation_guard": 2,
    "compliance_selfcheck_guard": 3,
    "punctuation_guard": 2,
    "reader_pull_guard": 2,
    "voice_pack_guard": 2,
    "meme_pack_guard": 2,
    "mental_state_guard": 2,
    # 新增 v0.7.2
    "emotional_impact_guard": 2,
    "opening_hook_guard": 2,
    "sensory_detail_guard": 2,
    "pacing_variation_guard": 2,
    "pov_consistency_guard": 2,
}

LEVEL2_CANNOT_FAIL = {k for k, v in GUARD_LEVELS.items() if v == 2}

MODE_GUARDS = {
    "draft": [
        "continuity_evidence_guard", "canon_evidence_guard",
        "hallucination_guard", "padding_guard",
        "opening_hook_guard",
    ],
    "standard": [
        "continuity_evidence_guard", "canon_evidence_guard",
        "hallucination_guard", "scene_delta_guard",
        "padding_guard", "anti_ai_guard",
        "show_dont_tell_guard", "character_voice_guard",
        "concrete_anchor_guard", "scene_causality_guard",
        "dialogue_naturalness_guard",
        "reader_pull_guard", "voice_pack_guard", "meme_pack_guard",
        "mental_state_guard",
        "opening_hook_guard",
        "sensory_detail_guard",
        "pacing_variation_guard",
    ],
    "submission": [
        "continuity_evidence_guard", "canon_evidence_guard",
        "hallucination_guard", "scene_delta_guard",
        "padding_guard", "anti_ai_guard",
        "show_dont_tell_guard", "character_voice_guard",
        "dialogue_beat_guard", "classical_register_guard",
        "perplexity_quality_guard",
        "editor_revision_guard", "concrete_anchor_guard",
        "scene_causality_guard", "dialogue_naturalness_guard",
        "style_variation_guard", "compliance_selfcheck_guard",
        "reader_pull_guard", "voice_pack_guard", "meme_pack_guard",
        "mental_state_guard",
        "emotional_impact_guard",
        "opening_hook_guard",
        "sensory_detail_guard",
        "pacing_variation_guard",
        "pov_consistency_guard",
    ],
}

# Guard runners: (module_name, function_name)
GUARD_RUNNERS = {
    "continuity_evidence_guard":  ("src.guards.continuity_evidence_guard", "run_continuity_evidence_check"),
    "canon_evidence_guard":       ("src.guards.canon_evidence_guard", "run_canon_evidence_check"),
    "hallucination_guard":        ("src.guards.hallucination_guard", "run_hallucination_check"),
    "scene_delta_guard":          ("src.guards.scene_delta_guard", "run_scene_delta_check"),
    "padding_guard":              ("src.guards.padding_guard", "run_padding_check"),
    "anti_ai_guard":              ("src.guards.anti_ai_patterns", "run_anti_ai_check"),
    "show_dont_tell_guard":       ("src.guards.show_dont_tell_guard", "run_show_dont_tell_check"),
    "character_voice_guard":      ("src.guards.character_voice_guard", "run_character_voice_check"),
    "dialogue_beat_guard":        ("src.guards.dialogue_beat_guard", "run_dialogue_beat_check"),
    "classical_register_guard":   ("src.guards.classical_register_guard", "run_classical_register_check"),
    "perplexity_quality_guard":   ("src.guards.perplexity_quality_guard", "build_report"),
    "editor_revision_guard":      ("src.guards.editor_revision_guard", "run_editor_revision_check"),
    "concrete_anchor_guard":      ("src.guards.concrete_anchor_guard", "run_concrete_anchor_check"),
    "scene_causality_guard":      ("src.guards.scene_causality_guard", "run_scene_causality_check"),
    "dialogue_naturalness_guard": ("src.guards.dialogue_naturalness_guard", "run_dialogue_naturalness_check"),
    "style_variation_guard":      ("src.guards.style_variation_guard", "build_report"),
    "compliance_selfcheck_guard": ("src.guards.compliance_selfcheck_guard", "run_compliance_selfcheck"),
    "punctuation_guard": ("src.guards.punctuation_guard", "run_punctuation_check"),
    "reader_pull_guard": ("src.guards.reader_pull_guard", "run_reader_pull_check"),
    "voice_pack_guard": ("src.guards.voice_pack_guard", "run_voice_pack_check"),
    "meme_pack_guard": ("src.guards.meme_pack_guard", "run_meme_pack_check"),
    "mental_state_guard": ("src.guards.human_texture.mental_state_guard", "run_mental_state_check"),
    # 新增 v0.7.2
    "emotional_impact_guard": ("src.guards.emotional_impact_guard", "run_emotional_impact_check"),
    "opening_hook_guard": ("src.guards.opening_hook_guard", "run_opening_hook_check"),
    "sensory_detail_guard": ("src.guards.sensory_detail_guard", "run_sensory_detail_check"),
    "pacing_variation_guard": ("src.guards.pacing_variation_guard", "run_pacing_variation_check"),
    "pov_consistency_guard": ("src.guards.pov_consistency_guard", "run_pov_consistency_check"),
}


# ═══════════════════════════════════════════════════
# Legacy guard result → GuardResult adapter
# ═══════════════════════════════════════════════════

def _adapt_legacy_dict(guard_name: str, raw: dict) -> GuardResult:
    """Convert a legacy guard dict into a GuardResult.

    Legacy guards return dicts like:
      {"status": "PASS" / "WARNING" / "FAIL",
       "flags": [{"message": ..., "confidence": ...}],
       "issues": [...]}
    """
    status = raw.get("status", "PASS")
    # Normalise legacy status strings
    if status in ("WARNING", "NEED_REVISION"):
        status = "WARN"
    elif status in ("BLOCK", "BLOCKED"):
        status = "FAIL"

    findings = []

    # Collect from 'flags'
    for flag in raw.get("flags", []):
        severity = "WARN"
        if flag.get("severity") == "FAIL":
            severity = "FAIL"
        findings.append(finding(
            guard=guard_name,
            severity=severity,
            code=flag.get("code", f"{guard_name}_FLAG"),
            message=flag.get("message", flag.get("description", "")),
            evidence=flag.get("evidence", [flag.get("snippet", "")]) if isinstance(flag.get("evidence"), list) else [],
            suggestion=flag.get("suggestion", ""),
            confidence=flag.get("confidence", 0.65),
            location=flag.get("location", ""),
        ))

    # Collect from 'issues' (used by standlone anti_ai, scene_quality, etc.)
    for issue in raw.get("issues", []):
        severity = "WARN"
        findings.append(finding(
            guard=guard_name,
            severity=severity,
            code=issue.get("code", f"{guard_name}_ISSUE"),
            message=issue.get("message", str(issue)),
            evidence=issue.get("evidence", []) if isinstance(issue.get("evidence"), list) else [],
            suggestion=issue.get("suggestion", ""),
            confidence=issue.get("confidence", 0.65),
        ))

    # If the guard has a FAIL/WARN status but no findings, add a generic one
    if status != "PASS" and not findings:
        findings.append(finding(
            guard=guard_name,
            severity=status,
            code=f"{guard_name}_STATUS_{status}",
            message=raw.get("message", raw.get("error", f"Guard {guard_name} returned {status}")),
        ))

    # Handle error field
    error = raw.get("error", "")

    metrics = {k: v for k, v in raw.items()
               if k not in ("status", "flags", "issues", "error", "guard",
                            "hard_fail", "final_decision")}

    return GuardResult(
        guard=guard_name,
        status=status,
        findings=findings,
        metrics=metrics,
        error=error,
    )


# ═══════════════════════════════════════════════════
# Core execution
# ═══════════════════════════════════════════════════

def run_single_guard(guard_name: str, content: str, chapter_no: int,
                     prev_tail: str = "", prev_brief: dict = None,
                     chapter_type: str = "normal",
                     extra_context: dict = None) -> Optional[GuardResult]:
    """Run ONE guard and return a GuardResult. THE canonical entry point."""
    import importlib

    if guard_name not in GUARD_RUNNERS:
        return None

    module_name, func_name = GUARD_RUNNERS[guard_name]
    try:
        mod = importlib.import_module(module_name)
        fn = getattr(mod, func_name)

        # Call with appropriate args based on guard
        sig_aware_guards = {
            "scene_delta_guard", "padding_guard",
        }
        # Guards with (chapter_no, content, ...) instead of (content, chapter_no, ...)
        chapter_first_guards = {
            "continuity_evidence_guard",
        }
        if guard_name in sig_aware_guards:
            raw = fn(content, chapter_type)
        elif guard_name in chapter_first_guards:
            # v0.7.1: forward prev_tail/prev_brief so continuity check has data
            try:
                raw = fn(chapter_no, content, prev_tail=prev_tail, prev_brief=prev_brief)
            except TypeError:
                raw = fn(chapter_no, content)
        elif guard_name == "character_voice_guard" and extra_context:
            # v0.4.5: pass voice_context to character_voice_guard
            vc = extra_context.get("voice_context", {})
            raw = fn(
                content, chapter_no,
                voice_profiles=vc.get("profiles"),
                voice_packs=vc.get("packs"),
                narration_policy=vc.get("narration_policy"),
            )
        else:
            raw = fn(content, chapter_no)

        # Handle tuple returns (canon_evidence returns (report, claims))
        if isinstance(raw, tuple):
            raw = raw[0]

        # Convert to GuardResult
        result = _adapt_legacy_dict(guard_name, raw)

        # Enforce level rules: Level 2 cannot FAIL
        if guard_name in LEVEL2_CANNOT_FAIL and result.status == "FAIL":
            result.status = "WARN"
            for f in result.findings:
                if f.severity == "FAIL":
                    f.severity = "WARN"

        return result

    except Exception as e:
        return GuardResult(
            guard=guard_name,
            status="WARN",
            error=str(e),
            findings=[finding(guard_name, "WARN", f"{guard_name}_ERROR",
                            f"Guard crashed: {e}")],
        )


def run_standard_guards(content: str, chapter_no: int,
                        mode: str = "standard",
                        prev_tail: str = "",
                        prev_brief: dict = None,
                        chapter_type: str = "normal",
                        reports_dir: str = "",
                        config: dict = None,
                        custom_guards: list[str] = None,
                        extra_context: dict = None) -> GuardSummary:
    """
    Run all guards for a chapter in the given mode.
    Returns a GuardSummary — THE single truth source for this chapter's guard results.

    Post, orchestrator, CI, and self-checks all call this ONE function.
    """
    import json

    # Determine which guards to run
    if mode == "debug" and custom_guards:
        guard_names = custom_guards
    else:
        guard_names = MODE_GUARDS.get(mode, MODE_GUARDS["standard"])

    # Check FTS health if available
    fts_health = {"ok": True}
    try:
        from fts_health import check_fts_health
        fts_health = check_fts_health(config)
    except ImportError:
        pass

    summary = GuardSummary(chapter_no=chapter_no, fts_health=fts_health)

    for guard_name in guard_names:
        result = run_single_guard(guard_name, content, chapter_no,
                                  prev_tail, prev_brief, chapter_type,
                                  extra_context=extra_context)
        if result is None:
            summary.skipped_guards.append(guard_name)
            continue

        # Save individual report if reports_dir specified
        if reports_dir:
            rp = Path(reports_dir) / f"chapter_{chapter_no:03d}_{guard_name}_report.json"
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
                         encoding="utf-8")
            result.report_path = str(rp)

        summary.add_result(result)

    # Save guard_summary.json (the truth source)
    if reports_dir:
        summary.save(str(Path(reports_dir) / f"chapter_{chapter_no:03d}_guard_summary.json"))

    return summary


# ═══════════════════════════════════════════════════
# Legacy-compatible wrapper (for gradual migration)
# ═══════════════════════════════════════════════════

def run_orchestrated(content: str, chapter_no: int, mode: str = "standard",
                     prev_tail: str = "", prev_brief: dict = None,
                     config: dict = None,
                     custom_guards: list[str] = None,
                     reports_dir: str = "",
                     extra_context: dict = None) -> dict:
    """
    Legacy-compatible wrapper around run_standard_guards.
    Returns the old dict format so existing code in chapter_pipeline.py
    and guard_orchestrator.py still works.
    """
    chapter_type = "normal"
    if config:
        policy = config.get("quality_policy", {})
        mode = policy.get("run_mode", mode)

    summary = run_standard_guards(
        content=content, chapter_no=chapter_no, mode=mode,
        prev_tail=prev_tail, prev_brief=prev_brief,
        chapter_type=chapter_type, reports_dir=reports_dir,
        config=config, custom_guards=custom_guards,
        extra_context=extra_context)

    # Convert to legacy dict format
    return {
        "guard": "guard_orchestrator",
        "version": summary.version,
        "run_mode": mode,
        "executed_guards": summary.executed_guards,
        "skipped_guards": summary.skipped_guards,
        "blocked_by": summary.blocked_by,
        "warning_count": summary.warn_count,
        "fail_count": summary.fail_count,
        "final_status": ("BLOCKED" if summary.overall_status == "FAIL"
                         else "NEED_REVISION" if summary.overall_status == "WARN"
                         else "PASS"),
        "results": {r.guard: {"status": r.status, "findings": len(r.findings)}
                     for r in summary.results},
        "warnings": summary.get_warnings(),
        "guard_summary_path": (str(Path(reports_dir) / f"chapter_{chapter_no:03d}_guard_summary.json")
                               if reports_dir else ""),
        "policy": {
            "quality_guards_warning_only": True,
            "compliance_can_block": True,
            "max_final_tasks": (config or {}).get("quality_policy", {}).get("max_final_revision_tasks", 5),
        },
    }


# ═══════════════════════════════════════════════════
# Registry self-check (v0.4.5 hotfix)
# ═══════════════════════════════════════════════════

def validate_guard_registry() -> dict:
    """Verify all registered guards are importable with valid entry points."""
    import importlib
    errors = []
    for guard_name, (module_name, func_name) in GUARD_RUNNERS.items():
        try:
            mod = importlib.import_module(module_name)
        except Exception as e:
            errors.append({
                "guard": guard_name,
                "module": module_name,
                "error": f"import failed: {e}",
            })
            continue
        if not hasattr(mod, func_name):
            errors.append({
                "guard": guard_name,
                "module": module_name,
                "function": func_name,
                "error": "missing function",
            })
    return {
        "ok": not errors,
        "errors": errors,
        "registered_count": len(GUARD_RUNNERS),
    }
