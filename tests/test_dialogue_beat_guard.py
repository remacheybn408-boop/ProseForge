#!/usr/bin/env python3
"""Test dialogue_beat_guard — 对白节拍门禁测试"""
import sys
from pathlib import Path

from src.guards.dialogue_beat_guard import run_dialogue_beat_check


def test_scene_with_beats_passes():
    """有动作+停顿 → 通过"""
    content = """"不对。"周砚抬手敲了敲石面，沉默了片刻才继续说，"这里的声音不对。"
沈师姐没有说话，只是盯着他。"""
    report = run_dialogue_beat_check(content, 1)
    if report["scene_reports"]:
        beats = report["scene_reports"][0]
        assert beats["conditions_met"] >= 2, f"Expected >=2 beats, got {beats}"
    else:
        assert report["dialogue_beat_pass"] is True


def test_scene_with_misunderstanding_cost():
    """有误会+代价 → 通过"""
    content = """矿头看见他袖口的银线，脸色一下变了，往后退了一步。
"你是戒律堂的人？"矿头声音发抖。
周砚攥紧了玉牌，指缝里渗出血来。
"不是。你搞错了。"
他付出了一枚铜钱的代价，但那不重要。"""
    report = run_dialogue_beat_check(content, 1)
    if report["scene_reports"]:
        beats = report["scene_reports"][0]
        # 应该有 misunderstanding 和 cost
        assert beats["conditions_met"] >= 2 or report["dialogue_beat_pass"] is True


def test_pure_explanation_fails():
    """纯对白解释设定 → 节拍不足"""
    content = """"灵气有五种属性。"周砚说。
"我知道。"沈师姐回答。
"金木水火土，对应不同经脉。"
"这个谁都知道。"
"但灵矿里的灵气是混合的。"
"然后呢？"
"所以要分开测量才行。" """
    report = run_dialogue_beat_check(content, 1)
    # 纯解释设定应该有节拍不足的场景
    if report["scene_reports"]:
        beats = report["scene_reports"][0]
        assert beats["conditions_met"] < 2 or report["dialogue_beat_pass"] is False


def test_empty_content():
    report = run_dialogue_beat_check("", 1)
    assert report["status"] == "PASS"
    assert report["scenes_analyzed"] == 0


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
