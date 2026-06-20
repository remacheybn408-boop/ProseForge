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

from src.utils.guard_result import (
    GuardResult, GuardSummary, GuardFinding,
    finding, result_pass, result_warn, result_fail,
)
from src.runtime import build_guard_context


# ═══════════════════════════════════════════════════
# Guard level definitions
# ═══════════════════════════════════════════════════

GUARD_LEVELS = {
    # L1 结构安全（4 个）
    "continuity_evidence_guard": 1,
    "canon_evidence_guard": 1,
    "hallucination_guard": 1,
    "scene_delta_guard": 1,
    # L2 质量聚合（5 个，v0.8.0 由 21 项整合而来）
    "scene_grounding_guard": 2,      # concrete_anchor + sensory_detail + scene_causality
    "narrative_rhythm_guard": 2,     # style_variation + pacing_variation + padding + punctuation + editor_revision
    "dialogue_quality_guard": 2,     # dialogue_beat + dialogue_structure + character_voice + meme_pack
    "prose_authenticity_guard": 2,   # anti_ai + show_dont_tell + perplexity_quality + classical_register + pov_consistency
    "reader_engagement_guard": 2,    # opening_hook + reader_pull + emotional_impact + character_psychology
    # L3 合规（1 个）
    "compliance_selfcheck_guard": 3,
}

LEVEL2_CANNOT_FAIL = {k for k, v in GUARD_LEVELS.items() if v == 2}

MODE_GUARDS = {
    "draft": [
        # 草稿模式：只跑 L1 安全 + 节奏/拉力两簇（够检测水文 + 开篇）
        "continuity_evidence_guard", "canon_evidence_guard",
        "hallucination_guard",
        "narrative_rhythm_guard", "reader_engagement_guard",
    ],
    "standard": [
        # Standard mode: L1 + all L2 aggregators. Compliance remains submission-only.
        "continuity_evidence_guard", "canon_evidence_guard",
        "hallucination_guard", "scene_delta_guard",
        "scene_grounding_guard", "narrative_rhythm_guard",
        "dialogue_quality_guard", "prose_authenticity_guard",
        "reader_engagement_guard",
    ],
    "submission": [
        # 投稿模式：全 10 个都跑
        "continuity_evidence_guard", "canon_evidence_guard",
        "hallucination_guard", "scene_delta_guard",
        "scene_grounding_guard", "narrative_rhythm_guard",
        "dialogue_quality_guard", "prose_authenticity_guard",
        "reader_engagement_guard",
        "compliance_selfcheck_guard",
    ],
}

# Guard runners: (module_name, function_name)
# v0.8.0：21 个旧 L2 guard 整合为 5 个聚合 guard，旧 guard 文件保留为子检测模块
GUARD_RUNNERS = {
    # L1
    "continuity_evidence_guard":  ("src.guards.continuity_evidence_guard", "run_continuity_evidence_check"),
    "canon_evidence_guard":       ("src.guards.canon_evidence_guard", "run_canon_evidence_check"),
    "hallucination_guard":        ("src.guards.hallucination_guard", "run_hallucination_check"),
    "scene_delta_guard":          ("src.guards.scene_delta_guard", "run_scene_delta_check"),
    # L2 聚合
    "scene_grounding_guard":      ("src.guards.scene_grounding_guard", "run_scene_grounding_check"),
    "narrative_rhythm_guard":     ("src.guards.narrative_rhythm_guard", "run_narrative_rhythm_check"),
    "dialogue_quality_guard":     ("src.guards.dialogue_quality_guard", "run_dialogue_quality_check"),
    "prose_authenticity_guard":   ("src.guards.prose_authenticity_guard", "run_prose_authenticity_check"),
    "reader_engagement_guard":    ("src.guards.reader_engagement_guard", "run_reader_engagement_check"),
    # L3
    "compliance_selfcheck_guard": ("src.guards.compliance_selfcheck_guard", "run_compliance_selfcheck"),
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
    # v0.8.0: L2 聚合 guard 通过 _cluster_aggregator 给每条 flag 打了 source=子检测名
    # （src/guards/_cluster_aggregator.py:104/110），adapter 这里把它读到 source_guard
    # 字段，保留子身份给 dedup / 最终报告使用。
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
            source_guard=flag.get("source", ""),
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
            source_guard=issue.get("source", ""),
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
        # (content, chapter_type) — L1 scene_delta_guard
        sig_aware_guards = {"scene_delta_guard"}
        # (content, chapter_no, chapter_type=...) — L2 narrative_rhythm aggregator (padding sub-check needs chapter_type)
        chapter_type_guards = {"narrative_rhythm_guard"}
        # (chapter_no, content, prev_tail, prev_brief) — L1 continuity
        chapter_first_guards = {"continuity_evidence_guard"}
        # (content, chapter_no, extra_context=...) — L2 aggregators that need voice/perplexity/character context
        extra_context_guards = {
            "dialogue_quality_guard",
            "prose_authenticity_guard",
            "reader_engagement_guard",
        }

        if guard_name in sig_aware_guards:
            raw = fn(content, chapter_type)
        elif guard_name in chapter_type_guards:
            raw = fn(content, chapter_no, chapter_type=chapter_type)
        elif guard_name in chapter_first_guards:
            # v0.7.1: forward prev_tail/prev_brief so continuity check has data
            try:
                raw = fn(chapter_no, content, prev_tail=prev_tail, prev_brief=prev_brief)
            except TypeError:
                raw = fn(chapter_no, content)
        elif guard_name in extra_context_guards:
            raw = fn(content, chapter_no, extra_context=extra_context)
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
    normalized_extra = build_guard_context(
        None,
        chapter_no=chapter_no,
        prev_brief=prev_brief,
        genre=(extra_context or {}).get("genre", ""),
        voice_context=(extra_context or {}).get("voice_context"),
        perplexity_config=config or {},
        extra=extra_context,
    )

    # Determine which guards to run
    if mode == "debug" and custom_guards:
        guard_names = custom_guards
    else:
        guard_names = MODE_GUARDS.get(mode, MODE_GUARDS["standard"])

    # Check FTS health if available
    fts_health = {"ok": True}
    try:
        from src.utils.fts_health import check_fts_health
        fts_health = check_fts_health(config)
    except ImportError:
        pass

    summary = GuardSummary(chapter_no=chapter_no, fts_health=fts_health)

    for guard_name in guard_names:
        result = run_single_guard(guard_name, content, chapter_no,
                                  prev_tail, prev_brief, chapter_type,
                                  extra_context=normalized_extra)
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
            "structural_can_block": True,        # L1 结构安全 guard FAIL 也走 BLOCKED
            "quality_guards_warning_only": True, # L2 在 registry 强降级为 WARN
            "compliance_can_block": True,        # L3 合规 FAIL 走 BLOCKED
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
