#!/usr/bin/env python3
"""
revision_loop_controller.py — 自动改稿闭环控制器 v0.4.0

串联完整流程:
  final_submission_report → revision_tasks → patch_plan
  → chapter_rewriter → guard_orchestrator 复查 → diff_report

三种模式:
  suggest:    只生成修改任务
  controlled: 生成 revised draft + diff report (默认, 推荐)
  aggressive: 默认关闭

用法:
  python scripts/revision_loop_controller.py \\
    --input chapter.txt --report final_report.json \\
    --mode controlled --max-rounds 2 \\
    --out-dir reports/revision_loop
"""
import json, sys, argparse, os
from pathlib import Path
from typing import Optional


DEFAULT_CONFIG = {
    "enabled": True,
    "version": "v0.4.0",
    "default_mode": "controlled",
    "max_rounds": 2,
    "auto_overwrite_source": False,
    "auto_ingest_revised": False,
    "require_user_approval": True,
    "only_fix_top_tasks": True,
    "max_tasks_per_round": 5,
    "min_task_confidence": 0.70,
    "preserve_chapter_ending": True,
    "preserve_character_voice": True,
    "preserve_dialect_and_classical_style": True,
    "preserve_foreshadowing": True,
    "max_changed_paragraph_ratio": 0.35,
    "allow_aggressive_mode": False,
    "rerun_guards_after_revision": True,
    "stop_if_quality_worse": True,
}


def run_suggest_mode(chapter_path: str, report_path: str,
                     out_dir: str, config: dict) -> dict:
    """suggest 模式: 只生成 revision_tasks.json"""
    from revision_task_generator import generate_tasks

    chapter = Path(chapter_path).read_text(encoding="utf-8")
    if not Path(report_path).exists():
        return {"status": "FAIL", "error": f"report not found: {report_path}"}
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))

    tasks = generate_tasks(
        chapter, report,
        config.get("min_task_confidence", 0.70),
        config.get("max_tasks_per_round", 5))

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    task_path = out / "revision_tasks.json"
    task_path.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"status": "OK", "tasks": str(task_path), "task_count": tasks["task_count"]}


def run_controlled_mode(chapter_path: str, report_path: str,
                        out_dir: str, config: dict) -> dict:
    """controlled 模式: 完整闭环"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Step 1: 生成修改任务
    from revision_task_generator import generate_tasks
    chapter = Path(chapter_path).read_text(encoding="utf-8")
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    tasks = generate_tasks(
        chapter, report,
        config.get("min_task_confidence", 0.70),
        config.get("max_tasks_per_round", 5))
    (out / "revision_tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [1/5] revision_tasks: {tasks['task_count']} tasks")

    if tasks["task_count"] == 0:
        return {"status": "OK", "message": "没有高置信度任务，跳过改稿。"}

    # Step 2: 规划补丁
    from patch_planner import build_patch_plan
    plan = build_patch_plan(
        chapter, tasks,
        config.get("max_changed_paragraph_ratio", 0.35))
    (out / "patch_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [2/5] patch_plan: {len(plan['patch_plan'])} ops, {plan['changed_ratio']:.0%}")

    # Step 3: 生成 revised draft
    from chapter_rewriter import rewrite_paragraphs, generate_rewrite_log
    from chapter_rewriter import split_paragraphs
    paras = split_paragraphs(chapter)
    new_paras, changed_ranges = rewrite_paragraphs(paras, plan, tasks)
    revised_text = "\n\n".join(new_paras)
    revised_path = out / "chapter.revised.txt"
    revised_path.write_text(revised_text, encoding="utf-8")
    log = generate_rewrite_log(chapter_path, str(revised_path), changed_ranges, len(paras))
    (out / "rewrite_log.json").write_text(
        json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [3/5] revised draft: {log['unchanged_ratio']:.0%} unchanged")

    # Step 4: 复查关键门禁
    if config.get("rerun_guards_after_revision", True):
        rerun_dir = out / "rerun_guards"
        rerun_dir.mkdir(exist_ok=True)
        # 只跑关键门禁
        try:
            from guard_orchestrator import run_orchestrated
            rerun = run_orchestrated(
                revised_text, tasks.get("chapter_no", 0),
                mode="draft", reports_dir=str(rerun_dir))
            (rerun_dir / "orchestrator_rerun.json").write_text(
                json.dumps(rerun, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  [4/5] rerun guards: {rerun['final_status']}")

            # 检查是否变差
            if config.get("stop_if_quality_worse", True):
                if rerun.get("blocked_by"):
                    return {"status": "REVISION_REJECTED",
                            "reason": f"改稿后合规风险: {rerun['blocked_by']}"}
        except Exception as e:
            print(f"  [4/5] rerun guards: skipped ({e})")

    # Step 5: diff report
    from revision_diff_report import generate_diff_report
    diff = generate_diff_report(chapter, revised_text, log, tasks.get("tasks", []))
    (out / "revision_diff_report.json").write_text(
        json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [5/5] diff report: {diff['recommendation']}")

    return {
        "status": "OK",
        "recommendation": diff.get("recommendation", "REVIEW_BEFORE_ACCEPT"),
        "outputs": {
            "revision_tasks": str(out / "revision_tasks.json"),
            "patch_plan": str(out / "patch_plan.json"),
            "revised_draft": str(out / "chapter.revised.txt"),
            "rewrite_log": str(out / "rewrite_log.json"),
            "diff_report": str(out / "revision_diff_report.json"),
        },
        "unchanged_ratio": log["unchanged_ratio"],
        "auto_overwrite_source": False,
        "auto_ingest_revised": False,
    }


def main():
    parser = argparse.ArgumentParser(description="Revision Loop Controller")
    parser.add_argument("--input", required=True, help="章节 TXT")
    parser.add_argument("--report", required=True, help="final_submission_report.json")
    parser.add_argument("--mode", default="controlled",
                        choices=["suggest", "controlled", "aggressive"])
    parser.add_argument("--max-rounds", type=int, default=2)
    parser.add_argument("--out-dir", required=True, help="输出目录")
    parser.add_argument("--config", default=None, help="config.json")
    args = parser.parse_args()

    cfg = dict(DEFAULT_CONFIG)
    if args.config and Path(args.config).exists():
        full = json.loads(Path(args.config).read_text(encoding="utf-8"))
        cfg = {**DEFAULT_CONFIG, **full.get("revision_loop", {})}

    if args.mode == "aggressive" and not cfg.get("allow_aggressive_mode", False):
        print("[BLOCK] aggressive 模式未启用。请在 config 中设置 allow_aggressive_mode=true")
        sys.exit(1)

    if args.mode == "suggest":
        result = run_suggest_mode(args.input, args.report, args.out_dir, cfg)
    elif args.mode in ("controlled", "aggressive"):
        result = run_controlled_mode(args.input, args.report, args.out_dir, cfg)
    else:
        result = {"status": "FAIL", "error": f"unknown mode: {args.mode}"}

    print(f"\n[{result.get('status','?')}] revision loop complete")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0 if result.get("status") in ("OK",) else 1


if __name__ == "__main__":
    sys.exit(main())
