#!/usr/bin/env python3
"""
final_submission_report.py — 最终投稿报告

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
from version import get_version


# ═══════════════════════════════════════════════════
# v0.8.0 兼容层：把 GuardResult.to_dict() 归一化到旧聚合格式
# ═══════════════════════════════════════════════════

_LIFT_FROM_METRICS = (
    "sub_scores", "sub_statuses", "score", "_guards_raw",
    "dialogue_structure_score", "opening_repetition_ratio",
    "sentence_len_cv", "abstract_word_count",
    "blocked_categories", "warnings_categories",
    "suggestions",
)


def _coerce_legacy(report: dict) -> dict:
    """把 v0.8.0 `GuardResult.to_dict()` 形态的报告转换成 aggregate_reports 期望的扁平结构。

    新格式: {status: PASS/WARN/FAIL, findings: [...], metrics: {_guards_raw, sub_scores, ...}}
    旧格式: {status: PASS/WARNING/BLOCK, flags: [...], suggestions: [...], _guards_raw, sub_scores, ...}

    本函数幂等：旧格式直接返回。
    """
    if not isinstance(report, dict):
        return {
            "status": "WARNING",
            "version": "unknown",
            "flags": [{
                "level": "WARNING",
                "type": "INVALID_REPORT_PAYLOAD",
                "message": f"Invalid guard report payload: {type(report).__name__}",
                "confidence": 1.0,
            }],
            "suggestions": ["检查 guard 报告序列化输出"],
        }
    out = dict(report)
    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}

    # 1) status 归一化到旧三值 PASS / WARNING / BLOCK
    st = (out.get("status") or "PASS").upper()
    if st in ("FAIL", "BLOCKED"):
        out["status"] = "BLOCK"
    elif st in ("WARN", "NEED_REVISION"):
        out["status"] = "WARNING"
    elif st == "PASS":
        out["status"] = "PASS"

    # 2) 把 metrics 里的常用字段提到顶层（不覆盖已有）
    for k in _LIFT_FROM_METRICS:
        if k not in out and k in metrics:
            out[k] = metrics[k]

    # 3) findings → flags 转换（新格式没有 flags，要造一份兼容旧 _extract_top_revision_tasks）
    findings = out.get("findings")
    if isinstance(findings, list) and "flags" not in out:
        flags = []
        sugs = []
        for f in findings:
            if not isinstance(f, dict):
                continue
            sev = (f.get("severity") or "WARN").upper()
            lvl = "BLOCK" if sev == "FAIL" else "WARNING"
            flags.append({
                "level": lvl,
                "type": f.get("code", ""),
                "message": f.get("message", ""),
                "confidence": f.get("confidence", 0.65),
                "source": f.get("guard", ""),
                "suggestion": f.get("suggestion", ""),
                "evidence": f.get("evidence", []) or [],
            })
            sug = f.get("suggestion")
            if sug:
                sugs.append(sug)
        out["flags"] = flags
        if sugs and "suggestions" not in out:
            out["suggestions"] = sugs

    return out


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

    # v0.8.0: 把 GuardResult.to_dict() 形态的报告归一化到旧扁平格式
    guard_reports = {name: _coerce_legacy(r) for name, r in guard_reports.items()}

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

        # v0.8.0: L2 聚合 guard 暴露子项分数 / 状态，方便上层定位是哪个子检测在喊
        if report.get("sub_scores"):
            summary["sub_scores"] = report["sub_scores"]
        if report.get("sub_statuses"):
            summary["sub_statuses"] = report["sub_statuses"]
        if report.get("score") is not None and "sub_scores" in report:
            summary["score"] = report["score"]

        # 提取关键指标（不同 guard 有不同字段；聚合 guard 走 _guards_raw 下钻）
        sub_reports = report.get("_guards_raw") or []
        metric_sources = [report] + [s for s in sub_reports if isinstance(s, dict)]
        for src in metric_sources:
            if "dialogue_structure_score" in src:
                summary["dialogue_structure_score"] = src["dialogue_structure_score"]
            if "opening_repetition_ratio" in src:
                summary["opening_repetition_ratio"] = src["opening_repetition_ratio"]
            if "sentence_len_cv" in src:
                summary["sentence_len_cv"] = src["sentence_len_cv"]
            if "abstract_word_count" in src:
                summary["abstract_word_count"] = src["abstract_word_count"]
            if "blocked_categories" in src:
                summary["blocked_categories"] = src["blocked_categories"]
            if "warnings_categories" in src:
                summary["warnings_categories"] = src["warnings_categories"]

        # 数 flags（聚合 guard 的 flags 已带 source 子名）
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
        "version": get_version(),
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
    v0.8.0: 聚合 guard 走 _guards_raw 下钻，子检测来源带 `parent::child` 形式。
    """
    tasks = []

    def _harvest(source_label: str, container: dict, parent_priority: str):
        for s in (container.get("suggestions") or [])[:3]:
            tasks.append({
                "source": source_label,
                "task": s if isinstance(s, str) else str(s),
                "priority": _infer_priority(source_label, container) or parent_priority,
            })
        for f in (container.get("flags") or [])[:2]:
            msg = f.get("message") if isinstance(f, dict) else str(f)
            lvl = f.get("level") if isinstance(f, dict) else None
            tasks.append({
                "source": source_label,
                "task": msg or str(f),
                "priority": lvl or "WARNING",
            })

    for guard_name, report in guard_reports.items():
        parent_priority = _infer_priority(guard_name, report)
        sub_reports = report.get("_guards_raw") or []

        if sub_reports:
            # 聚合 guard：从每个子检测下钻；顶层 suggestions 一般不存在，但兜底也扫一次
            _harvest(guard_name, report, parent_priority)
            for sub in sub_reports:
                if not isinstance(sub, dict):
                    continue
                sub_name = sub.get("guard", guard_name)
                _harvest(f"{guard_name}::{sub_name}", sub, parent_priority)
        else:
            _harvest(guard_name, report, parent_priority)

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
    """推断建议的优先级（兼容新旧 status 字符串）"""
    status = (report.get("status") or "PASS").upper()
    if status in ("BLOCK", "BLOCKED", "FAIL"):
        return "BLOCK"
    elif status in ("WARNING", "WARN", "NEED_REVISION"):
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
        "version": get_version(),
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


