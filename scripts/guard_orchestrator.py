#!/usr/bin/env python3
"""
guard_orchestrator.py — 门禁调度器 v0.4.0

分层执行门禁，支持 4 种运行模式，控制 WARNING/BLOCK 边界。
不直接检查文本，只负责决定跑哪些门禁、按什么顺序。

模式:
  draft:      快速检查 (continuity, hallucination, padding)
  standard:   日常模式 (balanced)
  submission: 投稿前完整检查 (all guards)
  debug:      指定单个或多个 guard

用法:
  python scripts/guard_orchestrator.py \\
    --input chapter.txt --chapter-no 1 --mode standard \\
    --config config.json --out orchestration_report.json
"""
import re, json, sys, argparse
from pathlib import Path
from typing import Optional

# ═══════════════════════════════════════════════════
# 门禁分层定义
# ═══════════════════════════════════════════════════

GUARD_LEVELS = {
    # Level 1: 结构安全层 (可 FAIL)
    "continuity_evidence_guard": 1,
    "canon_evidence_guard": 1,
    "hallucination_guard": 1,
    "scene_delta_guard": 1,
    # Level 2: 质量建议层 (只能 WARNING)
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
    # Level 3: 合规风险层 (可 BLOCK)
    "compliance_selfcheck_guard": 3,
}

# 模式定义: 哪些 guard 在哪种模式下执行
MODE_GUARDS = {
    "draft": [
        "continuity_evidence_guard", "canon_evidence_guard",
        "hallucination_guard", "padding_guard",
    ],
    "standard": [
        "continuity_evidence_guard", "canon_evidence_guard",
        "hallucination_guard", "scene_delta_guard",
        "padding_guard", "anti_ai_guard",
        "show_dont_tell_guard", "character_voice_guard",
        "concrete_anchor_guard", "scene_causality_guard",
        "dialogue_naturalness_guard",
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
    ],
}

# Level 2 guards can NEVER fail (hard rule)
LEVEL2_CANNOT_FAIL = {k for k, v in GUARD_LEVELS.items() if v == 2}


# ═══════════════════════════════════════════════════
# 调度逻辑
# ═══════════════════════════════════════════════════

def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def should_skip_heavy_guards(content: str, policy: dict) -> bool:
    """短章节自动跳过重门禁"""
    threshold = policy.get("short_chapter_threshold_chars", 1000)
    wc = count_chinese(content)
    return wc < threshold


def get_guards_for_mode(mode: str, content: str = "",
                        policy: Optional[dict] = None) -> list[str]:
    """获取当前模式应执行的 guard 列表"""
    guards = MODE_GUARDS.get(mode, MODE_GUARDS["standard"])

    if mode == "debug":
        return guards  # debug 模式下由用户指定

    policy = policy or {}
    if policy.get("skip_heavy_guards_for_short_chapters", True):
        if should_skip_heavy_guards(content, policy):
            heavy = {"perplexity_quality_guard", "style_variation_guard",
                     "editor_revision_guard"}
            guards = [g for g in guards if g not in heavy]

    return guards


def enforce_level_rules(report: dict, guard_name: str) -> dict:
    """强制门禁分层规则: Level 2 只能 WARNING, Level 3 可 BLOCK"""
    level = GUARD_LEVELS.get(guard_name, 2)

    if guard_name in LEVEL2_CANNOT_FAIL:
        # Force WARNING at most
        if report.get("status") == "FAIL":
            report["status"] = "WARNING"
        if report.get("final_decision") == "FAIL":
            report["final_decision"] = "WARNING"
        report["hard_fail"] = False

    return report


# ═══════════════════════════════════════════════════
# Guard 执行映射 (import-based, with fallback)
# ═══════════════════════════════════════════════════

GUARD_RUNNERS = {
    "continuity_evidence_guard": ("continuity_evidence_guard", "run_continuity_evidence_check"),
    "canon_evidence_guard": ("canon_evidence_guard", "run_canon_evidence_check"),
    "hallucination_guard": ("hallucination_guard", "run_hallucination_check"),
    "scene_delta_guard": ("scene_delta_guard", "run_scene_delta_check"),
    "padding_guard": ("padding_guard", "run_padding_check"),
    "anti_ai_guard": ("anti_ai_guard", "run_anti_ai_check"),
    "show_dont_tell_guard": ("show_dont_tell_guard", "run_show_dont_tell_check"),
    "character_voice_guard": ("character_voice_guard", "run_character_voice_check"),
    "dialogue_beat_guard": ("dialogue_beat_guard", "run_dialogue_beat_check"),
    "classical_register_guard": ("classical_register_guard", "run_classical_register_check"),
    "perplexity_quality_guard": ("perplexity_quality_guard", "build_report"),
    "editor_revision_guard": ("editor_revision_guard", "run_editor_revision_check"),
    "concrete_anchor_guard": ("concrete_anchor_guard", "run_concrete_anchor_check"),
    "scene_causality_guard": ("scene_causality_guard", "run_scene_causality_check"),
    "dialogue_naturalness_guard": ("dialogue_naturalness_guard", "run_dialogue_naturalness_check"),
    "style_variation_guard": ("style_variation_guard", "build_report"),
    "compliance_selfcheck_guard": ("compliance_selfcheck_guard", "run_compliance_selfcheck"),
}


import importlib


def run_guard(guard_name: str, content: str, chapter_no: int,
              prev_tail: str = "", prev_brief: dict = None,
              config: dict = None) -> Optional[dict]:
    """动态加载并运行单个 guard"""
    if guard_name not in GUARD_RUNNERS:
        return None

    module_name, func_name = GUARD_RUNNERS[guard_name]
    try:
        mod = importlib.import_module(module_name)
        fn = getattr(mod, func_name)
        return fn(content, chapter_no)
    except Exception as e:
        return {
            "guard": guard_name, "status": "WARNING",
            "error": str(e), "hard_fail": False
        }


def run_orchestrated(content: str, chapter_no: int, mode: str = "standard",
                     prev_tail: str = "", prev_brief: dict = None,
                     config: dict = None,
                     custom_guards: list[str] = None,
                     reports_dir: str = "") -> dict:
    """Orchestrate all guards for the given mode"""
    policy = config.get("quality_policy", {}) if config else {}

    if mode == "debug" and custom_guards:
        guards = custom_guards
    else:
        guards = get_guards_for_mode(mode, content, policy)

    results = {}
    warnings_list = []
    blocked = []
    skipped = []
    executed = []

    for guard_name in guards:
        result = run_guard(guard_name, content, chapter_no,
                          prev_tail, prev_brief, config)

        if result is None:
            skipped.append(guard_name)
            continue

        result = enforce_level_rules(result, guard_name)
        results[guard_name] = result
        executed.append(guard_name)

        # Save report
        if reports_dir:
            rp = Path(reports_dir) / f"chapter_{chapter_no:03d}_{guard_name}_report.json"
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                         encoding="utf-8")

        if result.get("status") in ("BLOCK", "BLOCKED"):
            blocked.append(guard_name)
        elif result.get("status") == "WARNING":
            # Extract warnings with confidence
            for flag in result.get("flags", []):
                flag["source_guard"] = guard_name
                flag.setdefault("confidence", 0.65)
                warnings_list.append(flag)

    # ── 构建调度报告 ──
    final_status = "PASS"
    if blocked:
        final_status = "BLOCKED"
    elif warnings_list:
        final_status = "NEED_REVISION"

    return {
        "guard": "guard_orchestrator",
        "version": "v0.4.0",
        "run_mode": mode,
        "executed_guards": executed,
        "skipped_guards": skipped,
        "blocked_by": blocked,
        "warning_count": len(warnings_list),
        "final_status": final_status,
        "results": results,
        "warnings": warnings_list,
        "policy": {
            "quality_guards_warning_only": True,
            "compliance_can_block": True,
            "max_final_tasks": policy.get("max_final_revision_tasks", 5),
        },
    }


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Guard Orchestrator")
    parser.add_argument("--input", required=True, help="章节 TXT")
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--mode", default="standard",
                        choices=["draft", "standard", "submission", "debug"])
    parser.add_argument("--config", default=None, help="config.json")
    parser.add_argument("--guards", default=None,
                        help="debug模式: 逗号分隔的 guard 名")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    config = {}
    if args.config and Path(args.config).exists():
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    content = Path(args.input).read_text(encoding="utf-8")

    custom_guards = None
    if args.mode == "debug" and args.guards:
        custom_guards = [g.strip() for g in args.guards.split(",")]

    report = run_orchestrated(content, args.chapter_no, args.mode,
                              config=config, custom_guards=custom_guards)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[{report['final_status']}] {report['run_mode']}: "
          f"{len(report['executed_guards'])} guards, "
          f"{report['warning_count']} warnings, "
          f"{len(report['blocked_by'])} blocked")

    return 0 if report["final_status"] != "BLOCKED" else 1


if __name__ == "__main__":
    sys.exit(main())
