#!/usr/bin/env python3
"""Test guard_contract_utils — 接口契约工具测试"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from guard_contract_utils import (
    guard_passed,
    normalize_chapter_no,
    ensure_guard_format,
    merge_guard_reports,
)


def test_guard_passed_status():
    assert guard_passed({"status": "PASS"}) is True
    assert guard_passed({"status": "FAIL"}) is False


def test_guard_passed_final_decision():
    assert guard_passed({"final_decision": "PASS"}) is True
    assert guard_passed({"final_decision": "FAIL"}) is False


def test_guard_passed_both():
    assert guard_passed({"status": "PASS", "final_decision": "PASS"}) is True


def test_guard_passed_non_dict():
    assert guard_passed(None) is False
    assert guard_passed("PASS") is False


def test_normalize_chapter_no_int():
    assert normalize_chapter_no(5) == 5


def test_normalize_chapter_no_str_number():
    assert normalize_chapter_no("5") == 5


def test_normalize_chapter_no_cn():
    assert normalize_chapter_no("第5章") == 5


def test_normalize_chapter_no_invalid():
    try:
        normalize_chapter_no("abc")
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_ensure_guard_format_defaults():
    report = ensure_guard_format({}, "test_guard")
    assert report["status"] == "PASS"
    assert report["final_decision"] == "PASS"
    assert report["errors"] == []
    assert report["warnings"] == []
    assert report["report_path"] == ""


def test_ensure_guard_format_status_only():
    report = ensure_guard_format({"status": "FAIL"})
    assert report["status"] == "FAIL"
    assert report["final_decision"] == "FAIL"


def test_merge_guard_reports_all_pass():
    merged = merge_guard_reports({
        "guard_a": {"status": "PASS"},
        "guard_b": {"status": "PASS", "final_decision": "PASS"},
    })
    assert merged["status"] == "PASS"


def test_merge_guard_reports_one_fail():
    merged = merge_guard_reports({
        "guard_a": {"status": "PASS"},
        "guard_b": {"status": "FAIL", "errors": ["bad thing"]},
    })
    assert merged["status"] == "FAIL"
    assert "guard_b" in merged["failed_guards"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
