#!/usr/bin/env python3
"""Test show_dont_tell_guard — AI总结句检测门禁测试"""
import sys
from pathlib import Path

from src.guards.show_dont_tell_guard import run_show_dont_tell_check


def test_clean_text_passes():
    content = "周砚走到矿壁前，伸手摸了摸湿漉漉的石面。他敲了敲石壁，声音沉闷。"
    report = run_show_dont_tell_check(content, 1)
    assert report["total_matches"] <= 2  # 干净的文本应该少于2个匹配
    assert report["show_dont_tell_pass"] is True


def test_realization_detected():
    """'他终于明白' 触发检测"""
    content = "他看着测灵铜钱上的裂纹，终于明白了，一直以来他理解错了灵力的运行方式。"
    report = run_show_dont_tell_check(content, 1)
    assert report["total_matches"] >= 1


def test_empty_crisis_detected():
    """'真正的危机才刚刚开始' 触发检测"""
    content = "周砚收起铜钱，望向矿洞深处。他有一种预感，真正的危机才刚刚开始。"
    report = run_show_dont_tell_check(content, 1)
    assert report["total_matches"] >= 1


def test_fate_gear_detected():
    """'命运的齿轮' 触发检测"""
    content = "那一刻，命运的齿轮开始转动，一切都将不再一样。"
    report = run_show_dont_tell_check(content, 1)
    assert report["total_matches"] >= 1


def test_action_expression_not_triggered():
    """动作化表达不触发检测"""
    content = "她把剑横在他喉前，声音很轻：'你刚才用的，不是本门术法。'"
    report = run_show_dont_tell_check(content, 1)
    assert report["total_matches"] == 0


def test_multiple_matches_warning():
    """多个匹配触发WARNING"""
    content = (
        "他终于明白了灵力的真相。真正的危机才刚刚开始。"
        "命运的齿轮已经开始转动，关系发生了微妙的变化。"
        "前所未有的恐惧笼罩着他。"
    )
    report = run_show_dont_tell_check(content, 1)
    # 应该有多个匹配
    assert report["total_matches"] >= 3


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
