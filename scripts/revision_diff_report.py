#!/usr/bin/env python3
"""
revision_diff_report.py — 改稿对比报告 v0.4.0

对比 source chapter 和 revised draft，生成 diff report。
让用户知道改了什么、改了多大、是否建议采用。

用法:
  python scripts/revision_diff_report.py \\
    --source chapter.txt --revised revised.txt \\
    --rewrite-log log.json --out diff_report.json
"""
import re, json, sys, argparse
from pathlib import Path


def split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in text.split("\n") if p.strip()]


def count_chinese(text: str) -> int:
    return len([c for c in text if '\u4e00' <= c <= '\u9fff'])


def compute_diff_summary(source_paras: list, revised_paras: list) -> dict:
    """计算改动统计"""
    src_chars = sum(count_chinese(p) for p in source_paras)
    rev_chars = sum(count_chinese(p) for p in revised_paras)

    changed = 0
    max_len = max(len(source_paras), len(revised_paras))
    for i in range(max_len):
        s = source_paras[i] if i < len(source_paras) else ""
        r = revised_paras[i] if i < len(revised_paras) else ""
        if s != r:
            changed += 1

    unchanged_ratio = 1.0 - changed / max(max_len, 1)

    return {
        "changed_paragraphs": changed,
        "unchanged_ratio": round(unchanged_ratio, 3),
        "source_chars": src_chars,
        "revised_chars": rev_chars,
        "added_chars": max(0, rev_chars - src_chars),
        "removed_chars": max(0, src_chars - rev_chars),
        "net_chars": rev_chars - src_chars,
    }


def compute_task_results(tasks: list, changed_ranges: list) -> list:
    """合并任务和改动范围，生成每个任务的结果"""
    range_by_task = {}
    for r in changed_ranges:
        tid = r.get("task_id", "")
        if tid not in range_by_task:
            range_by_task[tid] = []
        range_by_task[tid].append(r)

    results = []
    for task in tasks:
        tid = task["task_id"]
        ranges = range_by_task.get(tid, [])
        results.append({
            "task_id": tid,
            "status": "APPLIED" if ranges else "SKIPPED",
            "before_problem": task.get("problem", "")[:60],
            "after_change": task.get("instruction", "")[:80] if ranges else "未找到可修改范围",
        })
    return results


def generate_risk_flags(source_paras: list, revised_paras: list,
                        summary: dict) -> list:
    """检测改动是否过头"""
    flags = []
    if summary["unchanged_ratio"] >= 0.65:
        flags.append("改动比例低于 35%，风格保持较好")
    else:
        flags.append("改动比例超过 35%，请仔细审查")

    # 检测是否丢失了引号（对白）
    src_quotes = sum(1 for p in source_paras if '"' in p or '"' in p or '「' in p)
    rev_quotes = sum(1 for p in revised_paras if '"' in p or '"' in p or '「' in p)
    if rev_quotes < src_quotes * 0.8:
        flags.append("对白段落数量显著减少，可能丢失了角色对话")

    # 检测结尾是否被改动
    if source_paras[-2:] != revised_paras[-2:]:
        flags.append("章节结尾有改动，请确认钩子是否保留")

    return flags


def generate_diff_report(source_text: str, revised_text: str,
                         rewrite_log: dict,
                         tasks: list = None) -> dict:
    """生成完整 diff report"""
    source_paras = split_paragraphs(source_text)
    revised_paras = split_paragraphs(revised_text)

    summary = compute_diff_summary(source_paras, revised_paras)
    changed_ranges = rewrite_log.get("changed_ranges", [])
    task_results = compute_task_results(tasks or [], changed_ranges)
    risk_flags = generate_risk_flags(source_paras, revised_paras, summary)

    # 建议
    if summary["unchanged_ratio"] >= 0.65 and all(
            "丢失" not in f and "超过" not in f for f in risk_flags):
        recommendation = "REVIEW_BEFORE_ACCEPT"
    elif summary["unchanged_ratio"] >= 0.50:
        recommendation = "REVIEW_CAREFULLY"
    else:
        recommendation = "REVISION_REJECTED"

    chapter_no = rewrite_log.get("chapter_no", 0)

    return {
        "version": "v0.4.0",
        "chapter_no": chapter_no,
        "source_file": rewrite_log.get("source", ""),
        "revised_file": rewrite_log.get("output", ""),
        "summary": summary,
        "task_results": task_results,
        "risk_flags": risk_flags,
        "recommendation": recommendation,
    }


def main():
    parser = argparse.ArgumentParser(description="Revision Diff Report")
    parser.add_argument("--source", required=True, help="原文章节 TXT")
    parser.add_argument("--revised", required=True, help="revised draft TXT")
    parser.add_argument("--rewrite-log", required=True, help="rewrite_log.json")
    parser.add_argument("--out", required=True, help="输出 diff_report.json")
    args = parser.parse_args()

    source_text = Path(args.source).read_text(encoding="utf-8")
    revised_text = Path(args.revised).read_text(encoding="utf-8")
    log = json.loads(Path(args.rewrite_log).read_text(encoding="utf-8"))

    report = generate_diff_report(source_text, revised_text, log)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] diff report: {args.out}")
    print(f"  changed: {report['summary']['changed_paragraphs']} paragraphs")
    print(f"  net: {report['summary']['net_chars']:+d} chars")
    print(f"  recommendation: {report['recommendation']}")


if __name__ == "__main__":
    main()
