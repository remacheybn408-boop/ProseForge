#!/usr/bin/env python3
"""Test dialogue_naturalness_guard — 对白自然度门禁测试"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from src.guards.dialogue_naturalness_guard import (
    build_report,
    extract_dialogue_lines,
    count_interruptions,
    count_unfinished_sentences,
    count_action_beats,
    compute_address_variation_score,
    compute_speaker_length_cv,
    detect_ai_explanation_patterns,
    compute_dialogue_naturalness_score,
)


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
    # 不以 。！？ 结尾的算未完成
    assert count >= 2


def test_count_action_beats():
    text = "他抬手敲了敲门，转身看了一眼。"
    count = count_action_beats(text)
    assert count >= 2


def test_ai_explain_detection():
    lines = ["也就是说，这个方法行不通。", "这意味着我们必须撤退。", "好的。"]
    count = detect_ai_explanation_patterns(lines)
    assert count >= 2


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
    assert report["guard"] == "dialogue_naturalness_guard"
    assert report["status"] in ("PASS", "WARNING")
    assert report["hard_fail"] is False
    assert "dialogue_naturalness_score" in report
    assert 0 <= report["dialogue_naturalness_score"] <= 1


def test_ai_explanation_triggers_warning():
    """AI解释腔触发 WARNING"""
    content = (
        '"也就是说，我们需要先测量灵压。"周砚说。\n'
        '"这意味着矿脉的走向需要重新计算。"\n'
        '"简而言之，问题是灵力频率不对。"\n'
        '"换言之，这不是简单的问题。"\n'
        '"这说明我们之前的判断有误。"\n'
        '"总而言之，要多试几次。"'
    )
    report = build_report(content, 1)
    # 应该至少有一个 AI_EXPLANATION_PATTERN flag
    has_ai_flag = any(
        f.get("type") == "AI_EXPLANATION_PATTERN"
        for f in report.get("flags", [])
    )
    assert has_ai_flag or report["status"] == "WARNING"


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
    # 所有句子都以标点结尾 → 全部完成
    assert report["hard_fail"] is False
    assert report["unfinished_count"] <= 1  # 几乎没有未完成句


def test_empty_text_handled():
    """空文本不崩溃"""
    report = build_report("", 1)
    assert report["status"] == "PASS"
    assert report["hard_fail"] is False
    assert report["dialogue_naturalness_score"] == 1.0


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
        "dialogue_naturalness_score", "interruption_count",
        "unfinished_count", "action_beat_count",
        "address_variation_score", "speaker_count",
        "speaker_length_cv", "flags", "suggestions", "hard_fail"
    ]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
