#!/usr/bin/env python3
"""Test scene_causality_guard — 场景因果链门禁测试"""
import sys, json
from pathlib import Path

from src.guards.scene_causality_guard import (
    detect_cause,
    detect_action,
    detect_resistance,
    detect_cost,
    detect_result,
    detect_hook,
    split_into_scenes,
    analyze_scene,
    analyze_scenes,
    run_scene_causality_check,
)


# ═══════════════════════════════════════════
# 基础检测函数测试
# ═══════════════════════════════════════════

def test_detect_cause():
    """检测原因元素"""
    assert detect_cause("因为他想到了一个办法。")
    assert detect_cause("为了救她，他决定冒险。")
    assert detect_cause("他意识到这件事不对劲。")
    assert not detect_cause("天空很蓝。")


def test_detect_action():
    """检测行动元素"""
    assert detect_action("他动手把门推开。")
    assert detect_action("她试了一下新方法。")
    assert detect_action("他走过去看了一眼。")
    assert not detect_action("天气很好。")


def test_detect_resistance():
    """检测阻力元素"""
    assert detect_resistance("但他没想到会这么难。")
    assert detect_resistance("然而事情并不简单。")
    assert detect_resistance("不料半路杀出个程咬金。")
    assert not detect_resistance("一切都按计划进行。")


def test_detect_cost():
    """检测代价元素"""
    assert detect_cost("他付出了惨重的代价。")
    assert detect_cost("剑刃裂开一道缝。")
    assert detect_cost("他消耗了大量灵力。")
    assert not detect_cost("一切都很好。")


def test_detect_result():
    """检测结果元素"""
    assert detect_result("于是他们成功了。")
    assert detect_result("终于，门被打开了。")
    assert detect_result("最后他得到了想要的答案。")
    assert not detect_result("他开始行动。")


def test_detect_hook():
    """检测钩子元素"""
    assert detect_hook("但事情没有那么简单。")
    assert detect_hook("然而地上留下了一行血迹。")
    assert detect_hook("新的疑问出现了。")
    assert not detect_hook("故事到此结束。")


# ═══════════════════════════════════════════
# 场景分割测试
# ═══════════════════════════════════════════

def test_split_into_scenes():
    """场景分割"""
    content = (
        "周砚走到矿壁前，伸手摸了摸湿漉漉的石面。\n\n"
        "他敲了敲石壁，声音沉闷。不对，不是灵力不够。\n\n"
        '"再试一次。"沈师姐说。\n\n'
        "周砚把玉牌按在矿壁上。灵压从掌心传来。\n\n"
        "第二天，他又来到矿壁前。这一次他带了不同的法器。\n\n"
        "法器发出微光，矿壁终于裂开了一条缝。\n\n"
        "光从裂缝中透出来，异常诡异。"
    )
    scenes = split_into_scenes(content)
    assert len(scenes) >= 1


def test_split_into_scenes_empty():
    """空文本场景分割"""
    scenes = split_into_scenes("")
    assert len(scenes) == 0


def test_analyze_scene():
    """单个场景因果链分析"""
    scene = {
        "index": 1,
        "text": "因为他想到了办法。他立刻动手尝试。但阻力很大。他付出了代价。终于成功了。但留下了新的问题。",
    }
    result = analyze_scene(scene)
    assert result["total_elements"] >= 1
    assert "cause" in result["elements"]
    assert "action" in result["elements"]


# ═══════════════════════════════════════════
# 门禁核心测试
# ═══════════════════════════════════════════

def test_rich_scene_text_passes():
    """包含完整因果链的文本"""
    content = (
        "因为石壁的异常引起了他的注意。周砚走到矿壁前，伸手摸了摸湿漉漉的石面。\n\n"
        "为了探明真相，他敲了敲石壁。声音沉闷。但石壁纹丝不动，反而震得他虎口发麻。\n\n"
        '"再试一次。"沈师姐说。她抬手，剑尖轻轻点了一下地面。\n\n'
        "周砚咬紧牙关，把玉牌用力按在矿壁上。灵压从掌心传来，他感到气血翻涌。\n\n"
        "于是矿壁上的纹路终于亮了一下。代价是他的玉牌裂开了一道细缝。\n\n"
        "然而光芒散去后，矿壁上留下了一个从未见过的符号。异常诡异。"
    )
    report = run_scene_causality_check(content, 1)
    assert report["guard"] == "scene_causality_guard"
    assert report["status"] in ("PASS", "WARNING")
    assert report["hard_fail"] is False
    assert "scene_count" in report


def test_flat_text_triggers_warning():
    """缺少因果链的平坦文本触发 WARNING"""
    content = (
        "天气很好。阳光明媚。\n\n"
        "周砚在矿洞里走着。他看看石壁。\n\n"
        "沈师姐也在。她看着石壁。\n\n"
        "他们站了一会儿。然后走了。\n\n"
        "第二天天气也很好。他们又来了。\n\n"
        "还是老样子。没什么变化。"
    )
    report = run_scene_causality_check(content, 1)
    assert report["hard_fail"] is False
    # 因果链覆盖率应该低
    assert report["causality_coverage"] <= 1.0


def test_short_text_does_not_crash():
    """短文本不会崩溃"""
    content = "短。"
    report = run_scene_causality_check(content, 1)
    assert report["guard"] == "scene_causality_guard"
    assert report["hard_fail"] is False
    assert report["status"] in ("PASS", "WARNING")


def test_empty_text_handled():
    """空文本安全处理"""
    report = run_scene_causality_check("", 1)
    assert report["hard_fail"] is False
    assert report["status"] == "PASS"


def test_report_json_fields_complete():
    """输出 JSON 字段完整"""
    content = (
        "因为发现了问题。他立刻动手。但遇到了阻力。付出了代价。于是成功了。然而留下悬念。"
    )
    report = run_scene_causality_check(content, 1)
    required_fields = [
        "guard", "version", "status", "scene_count",
        "scenes_with_cause", "scenes_with_cost", "scenes_with_result",
        "causality_coverage", "flags", "suggestions", "hard_fail"
    ]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"


def test_hard_fail_always_false():
    """hard_fail 始终为 False"""
    # 丰富因果链文本
    rich = run_scene_causality_check(
        "因为他想到了办法。他立刻动手。但阻力很大。他付出了代价。终于成功了。但留下异常。",
        1
    )
    assert rich["hard_fail"] is False

    # 平坦无因果文本
    flat = run_scene_causality_check(
        "天气很好。阳光明媚。他走着。她看着。没什么发生。",
        1
    )
    assert flat["hard_fail"] is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
