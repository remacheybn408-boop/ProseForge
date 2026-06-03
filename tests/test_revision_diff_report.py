#!/usr/bin/env python3
"""Test revision_diff_report — 改稿对比报告测试"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from revision_diff_report import (
    generate_diff_report, compute_diff_summary,
    generate_risk_flags, split_paragraphs
)


def test_compute_diff_summary():
    src = ["段落一", "段落二", "段落三"]
    rev = ["段落一", "段落二改", "段落三"]
    summary = compute_diff_summary(src, rev)
    assert summary["changed_paragraphs"] == 1
    assert summary["unchanged_ratio"] > 0.6


def test_generate_diff_report():
    source = "段落一。\n\n段落二。\n\n段落三。"
    revised = "段落一。\n\n段落二已改。\n\n段落三。"
    log = {"source": "src.txt", "output": "rev.txt", "changed_ranges": [
        {"task_id": "rev_001", "paragraph_start": 2, "paragraph_end": 2,
         "change_type": "rewrite_range", "reason": "补代价"}]}
    report = generate_diff_report(source, revised, log)
    assert report["version"] == "v0.4.0"
    assert report["summary"]["changed_paragraphs"] >= 1
    assert report["recommendation"] in ("REVIEW_BEFORE_ACCEPT", "REVIEW_CAREFULLY", "REVISION_REJECTED")


def test_recommendation_low_change():
    source = "一段。\n\n二段。\n\n三段。\n\n四段。\n\n五段。\n\n六段。"
    revised = source  # no change
    log = {"source": "s", "output": "o", "changed_ranges": []}
    report = generate_diff_report(source, revised, log)
    assert report["recommendation"] == "REVIEW_BEFORE_ACCEPT"


def test_risk_flags_detect_quote_loss():
    src = ['"你好"他说。', '"再见"她答。', "结尾。"]
    rev = ["你好他说。", "再见她答。", "结尾。"]
    summary = {"unchanged_ratio": 0.8}
    flags = generate_risk_flags(src, rev, summary)
    assert any("对白" in f or "丢失" in f for f in flags)


def test_empty_reports_handled():
    report = generate_diff_report("", "", {"source": "", "output": "", "changed_ranges": []})
    assert report["version"] == "v0.4.0"


if __name__ == "__main__":
    import pytest; pytest.main([__file__, "-v"])
