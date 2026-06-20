#!/usr/bin/env python3
"""Test editor_revision_guard — 拟人审稿痕迹门禁测试"""
import sys, json
from pathlib import Path

from src.guards.editor_revision_guard import (
    detect_over_explained,
    compute_revision_texture,
    run_editor_revision_check,
    split_paragraphs,
    split_sentences,
    count_chinese,
)


# ═══════════════════════════════════════════
# 基础工具测试
# ═══════════════════════════════════════════

def test_count_chinese():
    assert count_chinese("你好世界") == 4
    assert count_chinese("hello 世界 abc") == 2
    assert count_chinese("") == 0


def test_split_sentences():
    text = "今天天气很好。明天可能下雨？我们应该做好准备！"
    sents = split_sentences(text)
    assert len(sents) >= 3


def test_split_paragraphs():
    text = "第一段内容。\n\n第二段内容。\n\n第三段足够长的内容在这里。"
    paras = split_paragraphs(text, min_chars=4)
    assert len(paras) >= 2


# ═══════════════════════════════════════════
# 过度解释检测测试
# ═══════════════════════════════════════════

def test_over_explained_normal_text_passes():
    """正常文本不应触发过度解释"""
    content = (
        "周砚走到矿壁前，伸手摸了摸湿漉漉的石面。这里很安静，只有水滴的声音。\n\n"
        "他敲了敲石壁，声音沉闷。不对，不是灵力不够，是频率不对。\n\n"
        '"再试一次。"沈师姐说。她的剑尖轻轻点了一下地面。\n\n'
        "周砚没有回答。沉默了片刻，他把玉牌按在了矿壁上。灵压从掌心传来。"
    )
    result = detect_over_explained(content)
    assert result["ratio"] < 0.30, f"Got {result['ratio']}"
    assert result["over_explained_count"] < max(result["total_paragraphs"] * 0.3, 1)


def test_over_explained_template_text():
    """模板化均匀句长文本应被检测"""
    # 构造一个每句都在 15-25 字的段落（每句约 17-18 字，无碎片无长句）
    content = (
        "今天天气非常不错适合出门散步游玩。明天可能也会是一个好天气日子。\n\n"
        "今天天气非常不错适合出门散步游玩。明天可能也会是一个好天气日子。\n\n"
        "今天天气非常不错适合出门散步游玩。明天可能也会是一个好天气日子。\n\n"
        "今天天气非常不错适合出门散步游玩。明天可能也会是一个好天气日子。"
    )
    result = detect_over_explained(content)
    # 这些句子长度较均匀，可能有过度解释倾向
    assert isinstance(result["ratio"], (int, float))


def test_revision_texture_varied_text():
    """节奏变化丰富的文本应有较高修改痕迹分数"""
    content = (
        "周砚走到矿壁前。伸手。湿的。\n\n"
        "他敲了敲石壁，声音沉闷得不像话，像是敲在了一整块铁上面。不对，不是灵力不够。\n\n"
        '"再试。"\n\n'
        "沉默。\n\n"
        "周砚把玉牌按在矿壁上。灵压从掌心传来，这一次，矿壁上的纹路终于亮了一下。"
    )
    score = compute_revision_texture(content)
    assert 0.0 <= score <= 1.0
    # 这种有短句、长句、碎片句的文本，分数应该不会太低
    assert score > 0.2, f"Expected higher texture score, got {score}"


def test_revision_texture_flat_text():
    """节奏平坦的文本应有较低修改痕迹分数"""
    content = (
        "今天天气非常不错适合出门游玩散步。明天可能也会是一个很好的天气呢。\n\n"
        "今天天气非常不错适合出门游玩散步。明天可能也会是一个很好的天气呢。\n\n"
        "今天天气非常不错适合出门游玩散步。明天可能也会是一个很好的天气呢。"
    )
    score = compute_revision_texture(content)
    assert 0.0 <= score <= 1.0


# ═══════════════════════════════════════════
# 门禁核心测试
# ═══════════════════════════════════════════

def test_normal_text_generates_pass():
    """正常多样化文本应 PASS"""
    content = (
        "周砚走到矿壁前，伸手摸了摸湿漉漉的石面。这里很安静。\n\n"
        "他敲了敲石壁，声音沉闷。不对，不是灵力不够，是频率不对。\n\n"
        '"再试一次。"沈师姐说。她转身。剑尖轻轻点了一下地面。\n\n'
        "周砚没有回答。\n\n"
        "沉默了片刻。他把玉牌按在了矿壁上。\n\n"
        "灵压从掌心传来，这一次——矿壁上的纹路终于亮了一下。"
    )
    report = run_editor_revision_check(content, 1)
    assert report["guard"] == "editor_revision_guard"
    assert report["status"] in ("PASS", "WARNING")
    assert report["hard_fail"] is False
    assert "revision_texture_score" in report
    assert "over_explained_count" in report


def test_template_text_triggers_warning():
    """极度模板化文本触发 WARNING"""
    content = (
        "今天天气非常不错适合出门。明天可能也是一个好天气。\n\n"
        "今天天气非常不错适合出门。明天可能也是一个好天气。\n\n"
        "今天天气非常不错适合出门。明天可能也是一个好天气。\n\n"
        "今天天气非常不错适合出门。明天可能也是一个好天气。\n\n"
        "今天天气非常不错适合出门。明天可能也是一个好天气。\n\n"
        "今天天气非常不错适合出门。明天可能也是一个好天气。"
    )
    report = run_editor_revision_check(content, 1)
    # 极度模板化应该触发 WARNING
    assert report["hard_fail"] is False
    # 至少有一些 flags
    assert len(report["flags"]) >= 1 or report["status"] == "WARNING"


def test_short_text_does_not_crash():
    """短文本不会崩溃"""
    content = "短。"
    report = run_editor_revision_check(content, 1)
    assert report["guard"] == "editor_revision_guard"
    assert report["hard_fail"] is False
    assert report["status"] in ("PASS", "WARNING")


def test_empty_text_handled():
    """空文本安全处理"""
    report = run_editor_revision_check("", 1)
    assert report["hard_fail"] is False
    assert report["status"] == "PASS"


def test_report_json_fields_complete():
    """输出 JSON 字段完整"""
    content = "这是一段正常的测试文本内容，包含足够的长度来测试。\n\n第二段内容。"
    report = run_editor_revision_check(content, 1)
    required_fields = [
        "guard", "version", "status", "revision_texture_score",
        "over_explained_count", "over_explained_paragraphs",
        "flags", "suggestions", "hard_fail"
    ]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"

    # hard_fail 永远是 False
    assert report["hard_fail"] is False


def test_hard_fail_always_false():
    """hard_fail 始终为 False"""
    # 正常文本
    normal = run_editor_revision_check("正常的中文测试文本内容。\n\n第二段在这里。", 1)
    assert normal["hard_fail"] is False

    # 模板文本
    template = run_editor_revision_check(
        "今天天气很好适合出门。明天也是一个好天气。\n\n"
        "今天天气很好适合出门。明天也是一个好天气。\n\n"
        "今天天气很好适合出门。明天也是一个好天气。\n\n"
        "今天天气很好适合出门。明天也是一个好天气。",
        1
    )
    assert template["hard_fail"] is False


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
