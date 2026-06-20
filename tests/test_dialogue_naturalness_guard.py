#!/usr/bin/env python3
"""Test dialogue_structure_guard — 对话结构门禁测试

历史: 由 dialogue_naturalness_guard 重构而来。v0.7.3 起:
  - 对话结构维度（打断/未完成/动作节拍/称呼/句长CV）留在 dialogue_structure_guard
  - AI_EXPLAIN_MARKER（"也就是说/这意味着"等）迁移到 anti_ai_guard
"""

from src.guards.dialogue_structure_guard import (
    build_report,
    extract_dialogue_lines,
    count_interruptions,
    count_unfinished_sentences,
    count_action_beats,
    compute_address_variation_score,
    compute_speaker_length_cv,
    compute_dialogue_structure_score,
)
from src.guards.anti_ai_guard import run_anti_ai_check_result


# ═══════════════════════════════════════════════════
# 工具函数测试
# ═══════════════════════════════════════════════════

def test_extract_dialogue_lines():
    text = '"你好。"她说。"今天天气不错。"他回答。'
    lines = extract_dialogue_lines(text)
    assert len(lines) == 2
    assert "你好" in lines[0]
    assert "今天天气不错" in lines[1]


def test_count_interruptions():
    lines = ["我还没说完——", "你等等……我", "知道了。"]
    assert count_interruptions(lines) >= 1


def test_count_unfinished_sentences():
    lines = ["我没说完", "这句说完了。", "还有"]
    count = count_unfinished_sentences(lines)
    assert count >= 2


def test_count_action_beats():
    text = "他抬手敲了敲门，转身看了一眼。"
    count = count_action_beats(text)
    assert count >= 2


def test_ai_explain_now_in_anti_ai_guard():
    """AI解释腔已迁移到 anti_ai_guard"""
    content = (
        "也就是说，这个方法行不通。\n"
        "这意味着我们必须撤退。\n"
        "简而言之，问题是灵力频率不对。"
    )
    report = run_anti_ai_check_result(content, 1)
    assert report["metrics"].get("ai_explain_count", 0) >= 2
    assert report["status"] == "WARNING"


# ═══════════════════════════════════════════════════
# 核心门禁测试
# ═══════════════════════════════════════════════════

def test_normal_dialogue_passes():
    """正常对白通过检查"""
    content = (
        '"不对。"周砚抬手敲了敲石面，沉默了片刻，'
        '"这里的声音——"\n'
        '"等等……"沈师姐打断了他，拔剑指向矿壁。\n'
        '"你看到了吗？那道纹路在亮。"\n'
        "周砚没有回答，他攥紧了玉牌，指缝里渗出细密的汗。\n"
        '"再给我一点时间。"他说。'
    )
    report = build_report(content, 1)
    assert report["guard"] == "dialogue_structure_guard"
    assert report["status"] in ("PASS", "WARNING")
    assert report["hard_fail"] is False
    assert "dialogue_structure_score" in report
    assert 0 <= report["dialogue_structure_score"] <= 1


def test_all_complete_sentences_warns():
    """所有对白都是完整句 → WARNING"""
    content = (
        '"今天天气很好。"她说。\n'
        '"确实如此。"他回答。\n'
        '"我们应该出门走走。"\n'
        '"这个提议非常好。"\n'
        '"那就这么决定了。"\n'
        '"好的没有问题。"'
    )
    report = build_report(content, 1)
    assert report["hard_fail"] is False
    assert report["unfinished_count"] <= 1


def test_empty_text_handled():
    """空文本不崩溃"""
    report = build_report("", 1)
    assert report["status"] == "PASS"
    assert report["hard_fail"] is False
    assert report["dialogue_structure_score"] == 1.0


def test_report_json_fields_complete():
    """输出 JSON 字段完整"""
    content = (
        '"你好。"他说。"你好吗？"她问。\n'
        '"我很好。"他抬手摸了摸鼻子。"真的。\n'
        '"那就好——"她突然停下。'
    )
    report = build_report(content, 1)
    required_fields = [
        "guard", "version", "status", "chapter_no",
        "dialogue_structure_score", "interruption_count",
        "unfinished_count", "action_beat_count",
        "address_variation_score", "speaker_count",
        "speaker_length_cv", "flags", "suggestions", "hard_fail",
    ]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
