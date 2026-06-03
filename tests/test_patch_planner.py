#!/usr/bin/env python3
"""Test patch_planner — 改稿补丁规划器测试"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from patch_planner import build_patch_plan, detect_locked_ranges, split_paragraphs


def test_detect_locked_ranges():
    paras = [
        "第一章开头，承接上一章内容。",
        "继续前面的故事。",
        "中间段落。",
        "伏笔：原来他真正的身份是...",
        "结尾钩子，留下悬念。",
    ]
    locked = detect_locked_ranges(paras)
    assert len(locked) >= 2  # 开头 + 结尾
    assert locked[0]["paragraph_start"] == 1  # 开头锁定


def test_build_patch_plan():
    chapter = "段落一。\n\n段落二。\n\n段落三。\n\n段落四。\n\n段落五。\n\n段落六。"
    tasks = {
        "tasks": [{
            "task_id": "rev_001",
            "type": "ADD_SCENE_COST",
            "confidence": 0.85,
            "instruction": "补代价",
            "target_range": {"paragraph_start": 3, "paragraph_end": 4},
        }]
    }
    plan = build_patch_plan(chapter, tasks)
    assert plan["version"] == "v0.4.0"
    assert len(plan["patch_plan"]) >= 1
    assert plan["changed_ratio"] <= 0.35


def test_locked_ranges_preserved():
    """锁定区域不会被改动"""
    chapter = "开头。\n\n中间段落。\n\n结尾钩子。"
    tasks = {
        "tasks": [{
            "task_id": "rev_001",
            "type": "ADD_SCENE_COST",
            "confidence": 0.85,
            "instruction": "补代价",
            "target_range": {"paragraph_start": 1, "paragraph_end": 1},
        }]
    }
    plan = build_patch_plan(chapter, tasks)
    # 开头被锁定，补丁不应包含段落1
    for op in plan["patch_plan"]:
        assert not (op["paragraph_start"] == 1 and op["paragraph_end"] == 1)


def test_warns_on_high_ratio():
    chapter = "短。\n\n短。\n\n短。"
    tasks = {"tasks": [
        {"task_id": "r1", "type": "ADD_SCENE_COST", "confidence": 0.85,
         "instruction": "补", "target_range": {"paragraph_start": 1, "paragraph_end": 3}},
        {"task_id": "r2", "type": "ADD_SCENE_COST", "confidence": 0.80,
         "instruction": "补", "target_range": {"paragraph_start": 2, "paragraph_end": 3}},
    ]}
    plan = build_patch_plan(chapter, tasks, max_changed_ratio=0.1)
    assert len(plan["warnings"]) >= 1


def test_empty_chapter():
    plan = build_patch_plan("", {"tasks": []})
    assert plan["total_paragraphs"] == 0


if __name__ == "__main__":
    import pytest; pytest.main([__file__, "-v"])
