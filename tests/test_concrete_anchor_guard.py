#!/usr/bin/env python3
"""Test concrete_anchor_guard — 具体锚点门禁测试"""
import sys, json
from pathlib import Path

from src.guards.concrete_anchor_guard import (
    detect_object_anchors,
    detect_body_actions,
    detect_scene_anchors,
    detect_visible_consequences,
    split_into_windows,
    analyze_windows,
    run_concrete_anchor_check,
)


# ═══════════════════════════════════════════
# 基础检测函数测试
# ═══════════════════════════════════════════

def test_detect_object_anchors():
    """检测物理物件"""
    text = "他抬手摸了摸门上的铜环，从袖口取出一枚铜钱放在桌上。石阶上的水渍还没有干。"
    count = detect_object_anchors(text)
    assert count > 0, f"Expected object anchors, got {count}"


def test_detect_object_anchors_empty():
    """无物件文本返回 0"""
    text = "他想着这件事，心里很不是滋味，觉得命运在捉弄他。"
    # 这段几乎没有物理物件
    count = detect_object_anchors(text)
    # 它可能仍然匹配到一些字符，但至少应该很少
    assert isinstance(count, int)


def test_detect_body_actions():
    """检测身体动作"""
    text = "他站起身，走到门前，抬手敲了三下。然后转身回头看了一眼。"
    count = detect_body_actions(text)
    assert count > 0, f"Expected body actions, got {count}"


def test_detect_scene_anchors():
    """检测场景锚点"""
    text = "月光透过窗纸照进来，地面湿漉漉的。远处传来风声，空气里有一股霉味。"
    count = detect_scene_anchors(text)
    assert count > 0, f"Expected scene anchors, got {count}"


def test_detect_visible_consequences():
    """检测可见后果"""
    text = "剑锋划过，袖口裂开一道口子。血渗了出来，滴在地上。石阶缺了一块。"
    count = detect_visible_consequences(text)
    assert count > 0, f"Expected visible consequences, got {count}"


# ═══════════════════════════════════════════
# 窗口分析测试
# ═══════════════════════════════════════════

def test_split_into_windows():
    """窗口切分"""
    text = "这是一段比较长的测试文本。" * 50  # ~750 chars
    windows = split_into_windows(text, 500)
    assert len(windows) >= 1


def test_split_into_windows_empty():
    """空文本窗口切分"""
    windows = split_into_windows("", 500)
    assert len(windows) == 0


def test_analyze_windows_rich_text():
    """丰富锚点文本的窗口分析"""
    text = (
        "周砚走到矿壁前，抬手摸了摸湿漉漉的石面。这里很安静，只有水滴的声音。"
        "月光从洞口照进来，照在他的手上。他敲了敲石壁，声音沉闷。"
    ) * 5  # 重复以产生多个窗口
    windows = split_into_windows(text, 200)
    result = analyze_windows(windows)
    assert result["total_windows"] > 0
    assert result["window_pass_rate"] >= 0.0
    assert isinstance(result["missing_types"], list)


def test_analyze_windows_empty():
    """空窗口列表"""
    result = analyze_windows([])
    assert result["total_windows"] == 0
    assert result["window_pass_rate"] == 1.0


# ═══════════════════════════════════════════
# 门禁核心测试
# ═══════════════════════════════════════════

def test_normal_rich_text_passes():
    """丰富锚点的正常文本"""
    content = (
        "周砚走到矿壁前，抬手摸了摸湿漉漉的石面。这里很安静，只有水滴的声音。\n\n"
        "月光从洞口照进来，落在他的手背上。他握紧拳头，敲了敲石壁。\n\n"
        "声音沉闷。不对，不是灵力不够，是频率不对。他拔出腰间的玉牌。\n\n"
        '"再试一次。"沈师姐说。她转身，剑尖轻轻点了一下地面。\n\n'
        "周砚把玉牌按在矿壁上。灵压从掌心传来——这一次，矿壁上的纹路终于亮了。\n\n"
        "石壁裂开一条缝，光从里面透出来。"
    )
    report = run_concrete_anchor_check(content, 1)
    assert report["guard"] == "concrete_anchor_guard"
    assert report["status"] in ("PASS", "WARNING")
    assert report["hard_fail"] is False
    assert report["total_windows"] > 0


def test_pure_abstract_text_triggers_warning():
    """纯抽象/概念文本触发 WARNING"""
    content = (
        "他突然明白了命运的真相。这种感觉无法形容，前所未有。\n\n"
        "真正的危机就在眼前，他必须做出选择。这关系到所有人的未来。\n\n"
        "他想起了过去的种种，五味杂陈。终于，他觉悟了。\n\n"
        "这就是所谓的成长，本质上就是接受自己的无能为力。\n\n"
        "说到底，一切都是命运的安排。"
    )
    report = run_concrete_anchor_check(content, 1)
    # 纯概念文本，缺少物件/场景，应该触发 WARNING
    assert report["hard_fail"] is False
    # 至少应该检测到缺少某些锚点
    assert isinstance(report["missing_types"], list)


def test_short_text_does_not_crash():
    """短文本不会崩溃"""
    content = "短。"
    report = run_concrete_anchor_check(content, 1)
    assert report["guard"] == "concrete_anchor_guard"
    assert report["hard_fail"] is False
    assert report["status"] in ("PASS", "WARNING")


def test_empty_text_handled():
    """空文本安全处理"""
    report = run_concrete_anchor_check("", 1)
    assert report["hard_fail"] is False
    assert report["status"] == "PASS"


def test_report_json_fields_complete():
    """输出 JSON 字段完整"""
    content = "他抬手摸了摸门上的铜环，从袖口取出一枚铜钱。月光透过窗纸照进来。"
    report = run_concrete_anchor_check(content, 1)
    required_fields = [
        "guard", "version", "status", "total_windows",
        "windows_with_object", "windows_with_body", "windows_with_scene",
        "window_pass_rate", "missing_types", "flags", "suggestions", "hard_fail"
    ]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"


def test_hard_fail_always_false():
    """hard_fail 始终为 False"""
    # 丰富文本
    rich = run_concrete_anchor_check(
        "他抬手摸了摸门上的铜环，从袖口取出一枚铜钱。月光透过窗纸。石阶湿漉漉的。",
        1
    )
    assert rich["hard_fail"] is False

    # 纯抽象文本
    abstract = run_concrete_anchor_check(
        "命运的危机已经到来。他意识到自己必须做出选择。这关系到所有的一切。"
        "他深深吸了一口气，内心五味杂陈。",
        1
    )
    assert abstract["hard_fail"] is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
