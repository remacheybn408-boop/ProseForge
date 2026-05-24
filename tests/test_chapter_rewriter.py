#!/usr/bin/env python3
"""Test chapter_rewriter — 章节改稿器测试"""
import sys, json, tempfile, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from chapter_rewriter import (
    rewrite_paragraphs, generate_rewrite_log,
    split_paragraphs, _apply_revision
)


def test_apply_revision_concrete():
    text = "他觉得这件事不对劲，心里很不舒服。"
    result = _apply_revision(text, "ADD_CONCRETE_DETAILS", "加物件", [])
    assert len(result) > len(text) or result == text


def test_apply_revision_cost():
    text = "战斗结束了，他站在原地没有动。"
    result = _apply_revision(text, "ADD_SCENE_COST", "补代价", [])
    assert len(result) >= len(text)


def test_apply_revision_no_change_short():
    text = "短。"
    result = _apply_revision(text, "ADD_SCENE_COST", "补", [])
    assert result == text  # 太短不改


def test_rewrite_paragraphs():
    chapter = "开头段落。\n\n中间问题段落。\n\n结尾钩子。"
    paras = split_paragraphs(chapter)
    tasks = {"tasks": [{
        "task_id": "rev_001", "type": "ADD_CONCRETE_DETAILS",
        "instruction": "加具体物件",
        "target_range": {"paragraph_start": 2, "paragraph_end": 2},
    }]}
    plan = {
        "patch_plan": [{
            "task_id": "rev_001", "operation": "rewrite_range",
            "paragraph_start": 2, "paragraph_end": 2,
            "rewrite_goal": "加具体物件",
        }],
        "locked_ranges": [{"paragraph_start": 1, "paragraph_end": 1,
                           "reason": "开头"}],
    }
    new_paras, changed = rewrite_paragraphs(paras, plan, tasks)
    assert len(new_paras) == len(paras)
    # 开头不变
    assert new_paras[0] == paras[0]


def test_generate_rewrite_log():
    log = generate_rewrite_log("src.txt", "out.txt", [], 10)
    assert log["auto_overwrite_source"] is False
    assert log["auto_ingest_revised"] is False
    assert log["version"] == "v0.4.0"


def test_locked_paragraphs_untouched():
    chapter = "锁定段落一。\n\n锁定段落二。\n\n可改段落。\n\n结尾钩子。"
    paras = split_paragraphs(chapter)
    tasks = {"tasks": [{"task_id": "r1", "type": "ADD_SCENE_COST",
              "instruction": "补", "target_range": {"paragraph_start": 1, "paragraph_end": 1}}]}
    plan = {
        "patch_plan": [{"task_id": "r1", "operation": "rewrite_range",
                        "paragraph_start": 1, "paragraph_end": 1,
                        "rewrite_goal": "补"}],
        "locked_ranges": [{"paragraph_start": 1, "paragraph_end": 2,
                           "reason": "锁定"}],
    }
    new_paras, _ = rewrite_paragraphs(paras, plan, tasks)
    assert new_paras[0] == paras[0]


if __name__ == "__main__":
    import pytest; pytest.main([__file__, "-v"])
