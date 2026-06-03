#!/usr/bin/env python3
"""
guard_contract_utils.py — Guard 接口契约工具 v0.3.1

统一 guard 返回格式、判断函数、chapter_no 规范化。
所有 guard 必须遵守此契约，CLI 是稳定接口，内部 import 不是。
"""
import re
import json


# ═══════════════════════════════════════════════════
# 统一 Guard 返回格式
# ═══════════════════════════════════════════════════

UNIFIED_GUARD_REPORT_SCHEMA = {
    "status": "PASS",          # "PASS" or "FAIL"
    "final_decision": "PASS",  # "PASS" or "FAIL" (alias for status)
    "errors": [],              # 致命错误列表
    "warnings": [],            # 非致命警告列表
    "report_path": "",         # 报告文件路径（如有）
}


def guard_passed(report):
    """
    统一判断 guard 是否通过。
    兼容 status 和 final_decision 两个字段。
    返回 True/False。
    """
    if not isinstance(report, dict):
        return False
    return report.get("status") == "PASS" or report.get("final_decision") == "PASS"


def normalize_chapter_no(value):
    """
    统一 chapter_no 规范化。
    接受 int 或 str（如 "第5章"、"5"），返回 int。
    无法解析时抛出 ValueError。
    """
    if isinstance(value, int):
        return value
    m = re.search(r'\d+', str(value))
    if not m:
        raise ValueError(f"无法解析 chapter_no: {value!r}")
    return int(m.group())


def ensure_guard_format(report, guard_name="unknown"):
    """
    确保 report 兼容统一格式。
    如果 report 缺少必要字段，补全默认值。
    返回修补后的 report。
    """
    if not isinstance(report, dict):
        report = {"raw": str(report)}

    # 确保 status 和 final_decision 一致
    if "status" not in report and "final_decision" in report:
        report["status"] = report["final_decision"]
    if "final_decision" not in report and "status" in report:
        report["final_decision"] = report["status"]

    report.setdefault("status", "PASS")
    report.setdefault("final_decision", report["status"])
    report.setdefault("errors", [])
    report.setdefault("warnings", [])
    report.setdefault("report_path", "")

    # 如果 guard 返回了格式不对的错误信息，转化为 errors
    if isinstance(report.get("error"), str):
        report["errors"].append(report["error"])
        del report["error"]

    return report


def merge_guard_reports(reports, stage="post_write"):
    """
    合并多个 guard report。
    任一 FAIL 则总结果 FAIL。
    返回合并后的 report dict。
    """
    merged = {
        "stage": stage,
        "status": "PASS",
        "final_decision": "PASS",
        "guards": {},
        "errors": [],
        "warnings": [],
        "failed_guards": [],
    }

    for guard_name, report in reports.items():
        if not isinstance(report, dict):
            merged["guards"][guard_name] = {"raw": str(report)}
            continue

        merged["guards"][guard_name] = report

        if not guard_passed(report):
            merged["status"] = "FAIL"
            merged["final_decision"] = "FAIL"
            merged["failed_guards"].append(guard_name)

        # 合并 errors
        for e in (report.get("errors") or []):
            merged["errors"].append(f"[{guard_name}] {e}")
        # 合并 warnings
        for w in (report.get("warnings") or []):
            merged["warnings"].append(f"[{guard_name}] {w}")

    return merged


# ═══════════════════════════════════════════════════
# CLI 调用推荐模式
# ═══════════════════════════════════════════════════

def cli_recommendation(guard_name):
    """
    返回该 guard 的推荐 CLI 调用方式。
    用于提示调用者优先使用 CLI 而非 import。
    """
    return f"推荐使用 CLI: python scripts/{guard_name}.py <args>"

