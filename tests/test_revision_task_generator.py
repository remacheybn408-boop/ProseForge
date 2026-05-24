#!/usr/bin/env python3
"""Test revision_task_generator — 修改任务生成器测试"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from revision_task_generator import generate_tasks


def test_generates_tasks_from_report():
    report = {
        "top_revision_tasks": [
            {"issue": "场景缺少代价", "confidence": 0.85, "fix": "补代价"},
            {"issue": "抽象总结过多", "confidence": 0.78, "fix": "加物件"},
        ],
        "chapter_no": 1,
    }
    chapter = "测试章节内容。\n\n" * 10
    tasks = generate_tasks(chapter, report)
    assert tasks["task_count"] >= 1
    assert tasks["version"] == "v0.4.0"


def test_low_confidence_filtered():
    report = {
        "top_revision_tasks": [
            {"issue": "小问题", "confidence": 0.55, "fix": "x"},
        ],
    }
    chapter = "测试" * 50
    tasks = generate_tasks(chapter, report, min_confidence=0.70)
    assert tasks["task_count"] == 0


def test_empty_report():
    report = {"top_revision_tasks": []}
    tasks = generate_tasks("测试", report)
    assert tasks["task_count"] == 0
    assert "没有" in tasks["message"]


def test_tasks_have_required_fields():
    report = {
        "top_revision_tasks": [
            {"issue": "test", "confidence": 0.80, "fix": "fix it"},
        ],
    }
    chapter = "测试内容。\n\n" * 20
    tasks = generate_tasks(chapter, report)
    if tasks["task_count"] > 0:
        t = tasks["tasks"][0]
        assert "task_id" in t
        assert "type" in t
        assert "must_keep" in t
        assert "avoid" in t


def test_max_tasks_limited():
    report = {"top_revision_tasks": [
        {"issue": f"issue {i}", "confidence": 0.80, "fix": f"fix {i}"}
        for i in range(10)]}
    chapter = "测试内容。\n\n" * 30
    tasks = generate_tasks(chapter, report, max_tasks=3)
    assert tasks["task_count"] <= 3


if __name__ == "__main__":
    import pytest; pytest.main([__file__, "-v"])
