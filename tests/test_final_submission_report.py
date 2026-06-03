#!/usr/bin/env python3
"""Test final_submission_report — 最终投稿报告聚合测试"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from final_submission_report import (
    aggregate_reports,
    load_reports_from_dir,
    _extract_top_revision_tasks,
    _generate_submission_advice,
)


# ═══════════════════════════════════════════════════
# 聚合测试
# ═══════════════════════════════════════════════════

def test_all_pass_yields_ready():
    """所有 PASS → READY"""
    reports = {
        "dialogue_naturalness_guard": {
            "guard": "dialogue_naturalness_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "dialogue_naturalness_score": 0.72,
            "flags": [],
            "suggestions": [],
            "hard_fail": False,
        },
        "style_variation_guard": {
            "guard": "style_variation_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "opening_repetition_ratio": 0.15,
            "sentence_len_cv": 0.45,
            "abstract_word_count": 5,
            "flags": [],
            "suggestions": [],
            "hard_fail": False,
        },
        "compliance_selfcheck_guard": {
            "guard": "compliance_selfcheck_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "blocked_categories": [],
            "warnings_categories": [],
            "flags": [],
            "suggestions": [],
            "hard_fail": False,
        },
    }
    result = aggregate_reports(reports, 1)
    assert result["overall_status"] in ("READY", "PASS")
    assert result["guard_count"] == 3
    # submission_advice should indicate readiness
    assert any(w in result.get("submission_advice", "").lower() for w in ["ready", "可以", "通过", "就绪"]) or result["overall_status"] in ("READY", "PASS")


def test_some_warnings_yields_need_revision():
    """部分 WARNING → NEED_REVISION"""
    reports = {
        "dialogue_naturalness_guard": {
            "guard": "dialogue_naturalness_guard",
            "version": "v0.4.0",
            "status": "WARNING",
            "flags": [
                {"level": "WARNING", "type": "NO_INTERRUPTIONS",
                 "message": "对话中没有打断。"}
            ],
            "suggestions": ["加入角色打断的场景。"],
            "hard_fail": False,
        },
        "style_variation_guard": {
            "guard": "style_variation_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "flags": [],
            "suggestions": [],
            "hard_fail": False,
        },
        "compliance_selfcheck_guard": {
            "guard": "compliance_selfcheck_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "blocked_categories": [],
            "warnings_categories": [],
            "flags": [],
            "suggestions": [],
            "hard_fail": False,
        },
    }
    result = aggregate_reports(reports, 1)
    assert result["overall_status"] == "NEED_REVISION"
    assert len(result["top_revision_tasks"]) >= 1


def test_any_block_yields_blocked():
    """任一 BLOCK → BLOCKED"""
    reports = {
        "dialogue_naturalness_guard": {
            "guard": "dialogue_naturalness_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "flags": [],
            "suggestions": [],
            "hard_fail": False,
        },
        "compliance_selfcheck_guard": {
            "guard": "compliance_selfcheck_guard",
            "version": "v0.4.0",
            "status": "BLOCK",
            "blocked_categories": ["explicit_sexual", "ad_spam"],
            "warnings_categories": [],
            "flags": [],
            "suggestions": ["检测到高风险内容"],
            "hard_fail": True,
        },
    }
    result = aggregate_reports(reports, 1)
    assert result["overall_status"] in ("BLOCKED", "BLOCK")
    assert any(w in result.get("submission_advice", "") for w in ["BLOCK", "block", "违规", "修改"])


def test_empty_reports_handled():
    """空报告列表不崩溃"""
    result = aggregate_reports({}, 1)
    assert result["overall_status"] == "READY"
    assert result["guard_count"] == 0
    assert isinstance(result["top_revision_tasks"], list)


def test_top_revision_tasks_extraction():
    """revision tasks 正确提取"""
    reports = {
        "guard_a": {
            "guard": "guard_a",
            "status": "WARNING",
            "flags": [
                {"level": "WARNING", "type": "ISSUE_1", "message": "问题一"},
                {"level": "WARNING", "type": "ISSUE_2", "message": "问题二"},
            ],
            "suggestions": ["建议一", "建议二", "建议三"],
            "hard_fail": False,
        },
    }
    result = aggregate_reports(reports, 1)
    tasks = result["top_revision_tasks"]
    assert len(tasks) <= 5
    assert all("task" in t for t in tasks)
    assert all("source" in t for t in tasks)


def test_aggregate_structure_complete():
    """聚合报告结构完整"""
    reports = {
        "test_guard": {
            "guard": "test_guard",
            "version": "v0.4.0",
            "status": "PASS",
            "flags": [],
            "suggestions": [],
            "hard_fail": False,
        },
    }
    result = aggregate_reports(reports, 3)
    required_fields = [
        "report_type", "version", "chapter_no", "overall_status",
        "guards", "guard_count", "top_revision_tasks",
        "submission_advice", "generated_at"
    ]
    for field in required_fields:
        assert field in result, f"Missing field: {field}"

    assert result["chapter_no"] == 3
    assert "test_guard" in result["guards"]


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
