#!/usr/bin/env python3
"""
final_submission_report.py — 最终投稿报告 v0.4.0

汇总所有门禁报告，生成投稿就绪状态摘要。

输入: {guard_name: report_dict} 的字典
输出: overall_status, guards 摘要, top_revision_tasks, submission_advice

overall_status:
- READY: 所有门禁 PASS
- NEED_REVISION: 部分 WARNING
- BLOCKED: 任一 BLOCK

CLI:
  python scripts/final_submission_report.py \
    --reports-dir exports/reports/ \
    --chapter-no 1 \
    --out final_report.json

或直接导入使用:
  from final_submission_report import aggregate_reports
  report = aggregate_reports(guard_reports, chapter_no)
"""
import json, sys, argparse, os
from pathlib import Path
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════
# 聚合逻辑
# ═══════════════════════════════════════════════════

def aggregate_reports(
    guard_reports: Dict[str, dict],
    chapter_no: int = 1
) -> dict:
    """
    聚合所有门禁报告。

    Args:
        guard_reports: {"guard_name": report_dict, ...}
        chapter_no: 章节编号

    Returns:
        聚合报告 dict
    """
    if not guard_reports:
        return _empty_aggregate(chapter_no)

    # ── 状态判定 ──
    statuses = []
    for name, report in guard_reports.items():
        st = report.get("status", "PASS")
        statuses.append({"guard": name, "status": st})

    any_blocked = any(s["status"] == "BLOCK" for s in statuses)
    any_warning = any(s["status"] == "WARNING" for s in statuses)

    if any_blocked:
        overall_status = "BLOCKED"
    elif any_warning:
        overall_status = "NEED_REVISION"
    else:
        overall_status = "READY"

    # ── 各 guard 摘要 ──
    guards_summary = {}
    for name, report in guard_reports.items():
        summary = {
            "status": report.get("status", "PASS"),
            "version": report.get("version", "unknown"),
        }

        # 提取关键指标（不同 guard 有不同字段）
        if "dialogue_naturalness_score" in report:
            summary["dialogue_naturalness_score"] = report["dialogue_naturalness_score"]
        if "opening_repetition_ratio" in report:
            summary["opening_repetition_ratio"] = report["opening_repetition_ratio"]
        if "sentence_len_cv" in report:
            summary["sentence_len_cv"] = report["sentence_len_cv"]
        if "abstract_word_count" in report:
            summary["abstract_word_count"] = report["abstract_word_count"]
        if "blocked_categories" in report:
            summary["blocked_categories"] = report["blocked_categories"]
        if "warnings_categories" in report:
            summary["warnings_categories"] = report["warnings_categories"]

        # 数 flags
        flags = report.get("flags", [])
        summary["flag_count"] = len(flags)

        guards_summary[name] = summary

    # ── 提取 top 5 修改任务 ──
    top_revision_tasks = _extract_top_revision_tasks(guard_reports)

    # ── 投稿建议 ──
    submission_advice = _generate_submission_advice(
        overall_status, guards_summary, guard_reports
    )

    return {
        "report_type": "final_submission_report",
        "version": "v0.4.0",
        "chapter_no": chapter_no,
        "overall_status": overall_status,
        "guards": guards_summary,
        "guard_count": len(guard_reports),
        "top_revision_tasks": top_revision_tasks,
        "submission_advice": submission_advice,
        "generated_at": _timestamp(),
    }


def _extract_top_revision_tasks(guard_reports: Dict[str, dict]) -> list:
    """
    从所有门禁中提取 top 5 修改建议。
    优先从 suggestions 和 flags 中提取。
    """
    tasks = []

    for guard_name, report in guard_reports.items():
        suggestions = report.get("suggestions", [])
        for s in suggestions[:3]:  # 每个 guard 最多取 3 条
            tasks.append({
                "source": guard_name,
                "task": s if isinstance(s, str) else str(s),
                "priority": _infer_priority(guard_name, report),
            })

        flags = report.get("flags", [])
        for f in flags[:2]:
            tasks.append({
                "source": guard_name,
                "task": f.get("message", str(f)),
                "priority": f.get("level", "WARNING"),
            })

    # 去重
    seen = set()
    unique_tasks = []
    for t in tasks:
        if t["task"] not in seen:
            seen.add(t["task"])
            unique_tasks.append(t)

    # 排序: BLOCK > WARNING > 其他
    priority_order = {"BLOCK": 0, "WARNING": 1, "PASS": 2}
    unique_tasks.sort(key=lambda t: priority_order.get(t["priority"], 3))

    return unique_tasks[:5]


def _infer_priority(guard_name: str, report: dict) -> str:
    """推断建议的优先级"""
    status = report.get("status", "PASS")
    if status == "BLOCK":
        return "BLOCK"
    elif status == "WARNING":
        return "WARNING"
    return "PASS"


def _generate_submission_advice(
    overall_status: str,
    guards_summary: dict,
    guard_reports: dict
) -> str:
    """生成人类可读的投稿建议"""
    if overall_status == "READY":
        advice = (
            "所有门禁检查均已通过。本章可以投稿。"
            "建议在投稿前通读一遍，确认无遗漏的错别字或格式问题。"
        )
    elif overall_status == "NEED_REVISION":
        warning_guards = [
            name for name, s in guards_summary.items()
            if s["status"] == "WARNING"
        ]
        advice = (
            f"部分门禁发出 WARNING: {', '.join(warning_guards)}。"
            f"建议根据上述 top_revision_tasks 中的建议逐条修改后重新检查。"
            f"这些 WARNING 不会阻止投稿，但修改后可显著提升文本质量。"
        )
    else:  # BLOCKED
        blocked_guards = []
        for name, report in guard_reports.items():
            if report.get("status") == "BLOCK":
                cats = report.get("blocked_categories", [])
                blocked_guards.append(f"{name}({', '.join(cats)})")
        advice = (
            f"检测到违规内容: {', '.join(blocked_guards)}。"
            f"这些内容必须修改后才能投稿，否则将被平台拒绝或下架。"
            f"请根据 risk_details 中的匹配内容逐一审查和修改。"
        )

    return advice


def _timestamp() -> str:
    """生成时间戳字符串"""
    from datetime import datetime
    return datetime.now().isoformat()


def _empty_aggregate(chapter_no: int) -> dict:
    return {
        "report_type": "final_submission_report",
        "version": "v0.4.0",
        "chapter_no": chapter_no,
        "overall_status": "READY",
        "guards": {},
        "guard_count": 0,
        "top_revision_tasks": [],
        "submission_advice": "无门禁报告，无法提供投稿建议。请先运行各门禁检查。",
        "generated_at": _timestamp(),
    }


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def load_reports_from_dir(reports_dir: str) -> Dict[str, dict]:
    """从目录加载所有 JSON 报告文件"""
    reports = {}
    dir_path = Path(reports_dir)

    if not dir_path.exists() or not dir_path.is_dir():
        print(f"警告: 目录不存在: {reports_dir}", file=sys.stderr)
        return reports

    for f in sorted(dir_path.glob("*.json")):
        try:
            report = json.loads(f.read_text(encoding="utf-8"))
            guard_name = report.get("guard", f.stem)
            reports[guard_name] = report
        except (json.JSONDecodeError, KeyError) as e:
            print(f"跳过 {f.name}: {e}", file=sys.stderr)

    return reports


def main():
    parser = argparse.ArgumentParser(description="Final Submission Report Aggregator")
    parser.add_argument(
        "--reports-dir",
        default="exports/reports/",
        help="门禁报告 JSON 目录"
    )
    parser.add_argument("--chapter-no", type=int, default=1)
    parser.add_argument("--out", default=None, help="输出 JSON 报告路径")
    args = parser.parse_args()

    guard_reports = load_reports_from_dir(args.reports_dir)
    report = aggregate_reports(guard_reports, args.chapter_no)

    print(json.dumps(report, ensure_ascii=False, indent=2))

    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    print(f"\nOverall: {report['overall_status']}")
    print(f"Guards: {report['guard_count']}")
    print(f"Tasks: {len(report['top_revision_tasks'])}")


if __name__ == "__main__":
    main()
