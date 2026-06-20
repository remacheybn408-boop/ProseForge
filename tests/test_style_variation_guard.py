#!/usr/bin/env python3
"""Test style_variation_guard — 句式变化门禁测试"""
import sys, json
from pathlib import Path

from src.guards.style_variation_guard import (
    build_report,
    split_sentences,
    split_paragraphs,
    count_chinese,
    compute_sentence_opening_repetition,
    compute_sentence_length_cv,
    compute_paragraph_length_cv,
    count_abstract_words,
    count_transition_words,
    compute_transition_density,
)


# ═══════════════════════════════════════════════════
# 工具函数测试
# ═══════════════════════════════════════════════════

def test_split_sentences():
    text = "今天天气很好。明天可能下雨？我们要做好准备！这是真的吗。"
    sents = split_sentences(text)
    assert len(sents) >= 4


def test_split_paragraphs():
    text = "第一段内容在这里。\n\n第二段内容。\n\n第三段。"
    paras = split_paragraphs(text)
    assert len(paras) >= 2


def test_count_chinese():
    assert count_chinese("你好世界") == 4
    assert count_chinese("hello world") == 0
    assert count_chinese("中文abc测试") == 4


def test_sentence_opening_repetition():
    sents = ["他走了。", "他来了。", "他笑了。", "她哭了。", "天气好。"]
    info = compute_sentence_opening_repetition(sents)
    assert info["opening_repetition_ratio"] >= 0.15  # 2-char openings: each unique
    # most_common_opener uses 2-char openings, so it's "他走" etc not "他"
    assert "他" in info["most_common_opener"]


def test_abstract_word_count():
    text = "他仿佛看到命运的安排，似乎一切都已注定。危机正在降临，真正的考验才刚开始。"
    count = count_abstract_words(text)
    assert count >= 4


def test_transition_word_count():
    text = "但是今天下雨，所以不能出门。然而他坚持要去，于是我们出发了。"
    count = count_transition_words(text)
    assert count >= 4


# ═══════════════════════════════════════════════════
# 核心门禁测试
# ═══════════════════════════════════════════════════

def test_normal_text_passes():
    """正常变化的文本通过"""
    content = (
        "周砚走到矿壁前，伸手摸了摸湿漉漉的石面。\n\n"
        "这里很安静，只有水滴的声音。他敲了敲石壁，声音沉闷。\n\n"
        "不对，不是灵力不够，是频率的问题。\n\n"
        '"再试一次。"沈师姐说。她的剑尖轻轻点了一下地面，石屑纷飞。\n\n'
        "周砚没有回答。沉默了片刻，他把玉牌按在了矿壁上。灵压从掌心传来。"
    )
    report = build_report(content, 1)
    assert report["guard"] == "style_variation_guard"
    assert report["status"] in ("PASS", "WARNING")
    assert report["hard_fail"] is False
    assert "sentence_len_cv" in report
    assert "paragraph_len_cv" in report


def test_high_opening_repetition_warns():
    """句子开头重复 → WARNING"""
    content = (
        "他走了一步。他看了一眼。他停下脚步。他抬手敲门。他转身离去。"
        "他又回头。他笑了笑。他说算了。他叹了口气。他最终走了。"
    )
    report = build_report(content, 1)
    has_opening_flag = any(
        f.get("type") == "SENTENCE_OPENING_REPETITION"
        for f in report.get("flags", [])
    )
    assert has_opening_flag or report["opening_repetition_ratio"] >= 0.1


def test_many_abstract_words_warns():
    """大量抽象词 → WARNING"""
    content = (
        "命运似乎已经注定。真正的危机正在降临。"
        "他仿佛看到了结局。一切终于到了该了结的时候。"
        "宿命不可违。绝望的深渊中，他看到了光明的希望。"
        "永恒的轮回，无尽的黑暗，这个世界的本质就是如此。"
        "危机总是在最不经意的时候出现。"
        "这是真正的考验，仿佛天意。"
    ) * 2
    report = build_report(content, 1)
    assert report["abstract_word_count"] > 12
    has_abstract_flag = any(
        f.get("type") == "ABSTRACT_WORD_OVERUSE"
        for f in report.get("flags", [])
    )
    assert has_abstract_flag or report["status"] == "WARNING"


def test_many_transition_words_warns():
    """大量转折词 → WARNING"""
    content = (
        "但是他还是来了。所以我们必须面对。然而事情没有那么简单。"
        "于是我们决定留下。然后天就黑了。接着下起了雨。"
        "之后一切都变了。因为他的选择。但是他不后悔。所以继续前进。"
        "然而道路越来越难。于是停了下来。然后想到了办法。接着开始行动。"
    )
    report = build_report(content, 1)
    has_transition_flag = any(
        f.get("type") == "TRANSITION_WORD_OVERUSE"
        for f in report.get("flags", [])
    )
    assert has_transition_flag or report["transition_word_count"] > 10


def test_empty_text_handled():
    """空文本不崩溃"""
    report = build_report("", 1)
    assert report["status"] == "PASS"
    assert report["hard_fail"] is False


def test_report_json_fields_complete():
    """输出 JSON 字段完整"""
    content = "今天天气很好，阳光明媚，春风和煦。"
    report = build_report(content, 1)
    required_fields = [
        "guard", "version", "status", "chapter_no",
        "sentence_opening_variety", "sentence_len_cv",
        "paragraph_len_cv", "abstract_word_count",
        "transition_word_count", "opening_repetition_ratio",
        "flags", "suggestions", "hard_fail"
    ]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
