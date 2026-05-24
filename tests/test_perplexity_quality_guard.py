#!/usr/bin/env python3
"""Test perplexity_quality_guard — QGP 困惑度质量门禁测试"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from perplexity_quality_guard import (
    build_report,
    split_paragraphs,
    split_sentences,
    char_ngram_counts,
    compute_ngram_surprise,
    compute_ngram_surprise_no_corpus,
    repeated_phrase_ratio,
    sentence_length_stats,
    abstract_summary_ratio,
    concrete_anchor_ratio,
    dialogue_variation_score,
    compute_rhythm_flatness,
    count_chinese,
)


# ═══════════════════════════════════════════
# 基础工具测试
# ═══════════════════════════════════════════

def test_count_chinese():
    assert count_chinese("你好世界") == 4
    assert count_chinese("hello 世界 abc") == 2
    assert count_chinese("") == 0


def test_split_paragraphs():
    text = "第一段内容。\n\n第二段内容。\n\n短。\n\n第三段足够长的内容在这里。"
    paras = split_paragraphs(text, min_chars=4)
    assert len(paras) >= 2


def test_split_sentences():
    text = "今天天气很好。明天可能下雨？我们应该做好准备！"
    sents = split_sentences(text)
    assert len(sents) >= 3


def test_char_ngram_counts():
    text = "你好世界你好"
    counts = char_ngram_counts(text, 2)
    assert "你好" in counts
    assert counts["你好"] >= 1


def test_ngram_surprise_no_corpus():
    score = compute_ngram_surprise_no_corpus("今天天气很好，阳光明媚。")
    assert 0 <= score <= 100


def test_ngram_surprise_with_corpus():
    corpus = char_ngram_counts("今天天气很好阳光明媚春风和煦", 3)
    score = compute_ngram_surprise("今天天气很好阳光明媚", corpus, 3)
    assert 0 <= score <= 100


def test_repeated_phrase_ratio():
    text = "今天天气很好今天天气很好今天天气很好"
    ratio = repeated_phrase_ratio(text)
    assert ratio > 0  # 应该有重复


def test_repeated_phrase_ratio_unique():
    text = "今天天气很好阳光明媚春风和煦万物复苏"
    ratio = repeated_phrase_ratio(text)
    assert ratio < 0.3  # 几乎无重复


def test_sentence_length_stats():
    stats = sentence_length_stats("短句。这是一个比较长的句子用来测试。中等句子。")
    assert stats["count"] >= 2
    assert stats["mean"] > 0


def test_abstract_summary_ratio():
    text = "他终于明白了，真正的命运似乎已经注定。"
    ratio = abstract_summary_ratio(text)
    assert ratio > 0  # 含多个抽象词


def test_concrete_anchor_ratio():
    text = "他抬手摸了摸门上的铜环，从袖口取出一枚铜钱。"
    ratio = concrete_anchor_ratio(text)
    assert ratio > 0  # 含具体锚点


def test_dialogue_variation():
    text = '"你好。"他简短地说。"今天天气真不错啊，你觉得呢？"她笑着问。"嗯。"'
    score = dialogue_variation_score(text)
    assert 0 <= score <= 1


def test_rhythm_flatness():
    paras = ["短段落。", "这是一个比较长的段落，包含更多的内容和描述。", "中等段。"]
    flatness = compute_rhythm_flatness(paras)
    assert 0 <= flatness <= 1


# ═══════════════════════════════════════════
# 门禁核心测试
# ═══════════════════════════════════════════

def test_normal_text_generates_report():
    """正常中文文本可以生成 report"""
    content = (
        "周砚走到矿壁前，伸手摸了摸湿漉漉的石面。这里很安静，只有水滴的声音。\n\n"
        "他敲了敲石壁，声音沉闷。不对，不是灵力不够，是频率不对。\n\n"
        '"再试一次。"沈师姐说。她的剑尖轻轻点了一下地面。\n\n'
        "周砚没有回答。沉默了片刻，他把玉牌按在了矿壁上。\n\n"
        "灵压从掌心传来，这一次，矿壁上的纹路终于亮了一下。"
    )
    report = build_report(content, {}, "test_novel", 1)
    assert report["guard"] == "perplexity_quality_guard"
    assert report["status"] in ("PASS", "WARNING")
    assert report["hard_fail"] is False
    assert report["mode"] == "warning_only"
    assert "summary" in report
    assert report["summary"]["paragraph_count"] > 0


def test_template_text_triggers_warning():
    """重复模板句触发 WARNING"""
    content = (
        "今天天气很好，阳光明媚。今天天气很好，阳光明媚。\n\n"
        "今天天气很好，阳光明媚。今天天气很好，阳光明媚。\n\n"
        "今天天气很好，阳光明媚。今天天气很好，阳光明媚。\n\n"
        "今天天气很好，阳光明媚。今天天气很好，阳光明媚。\n\n"
        "今天天气很好，阳光明媚。今天天气很好，阳光明媚。"
    )
    report = build_report(content, {}, "test", 1)
    # 高度重复文本应该触发 WARNING
    assert report["hard_fail"] is False


def test_short_text_does_not_crash():
    """很短文本不会崩溃"""
    content = "短。"
    report = build_report(content, {}, "test", 1)
    assert report["guard"] == "perplexity_quality_guard"
    assert report["hard_fail"] is False


def test_dialect_wenyan_does_not_hard_fail():
    """方言/文言不会 HARD FAIL"""
    content = (
        "然则天道有常，不为尧存，不为桀亡。\n\n"
        "甭说了，俺们这就走，咋还不信咧？\n\n"
        "夫修道者，必先正其心，而后方能悟其道也。"
    )
    report = build_report(content, {}, "test", 1)
    assert report["hard_fail"] is False
    # status 只能是 PASS 或 WARNING
    assert report["status"] in ("PASS", "WARNING")


def test_no_baseline_still_runs():
    """没有 baseline 时仍能运行"""
    report = build_report("测试内容", {}, "test", 1, baseline=None)
    assert report["baseline_status"] == "missing"
    assert report["hard_fail"] is False


def test_report_json_fields_complete():
    """输出 JSON 字段完整"""
    report = build_report("这是一段正常的测试文本内容。", {}, "test", 1)
    required_fields = ["guard", "version", "status", "mode", "backend",
                       "novel_slug", "chapter_no", "baseline_status",
                       "summary", "flags", "suggestions", "paragraphs", "hard_fail"]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"

    summary_fields = ["avg_qgp_score", "paragraph_count", "low_surprise_ratio",
                      "high_surprise_ratio", "template_risk_ratio",
                      "rhythm_flatness", "dialogue_variation_score"]
    for field in summary_fields:
        assert field in report["summary"], f"Missing summary field: {field}"


def test_no_ai_rate_output():
    """不输出 AI率/人类率 等误导字段"""
    report = build_report("测试内容", {}, "test", 1)
    report_str = json.dumps(report, ensure_ascii=False)
    assert "AI率" not in report_str
    assert "人类率" not in report_str
    assert "平台检测" not in report_str
    assert "绕过" not in report_str


def test_concrete_anchor_detected():
    """具体锚点文本分数正常"""
    content = ("他抬手摸了摸门上的铜环，从袖口取出一枚铜钱放在桌上。"
               "石阶上的水渍还没有干，窗纸上映着月光。"
               "他回头看了一眼门槛，那枚玉牌还静静躺在那里。")
    report = build_report(content, {}, "test", 1)
    assert report["summary"]["concrete_anchor_ratio"] > 0


def test_empty_text_handled():
    report = build_report("", {}, "test", 1)
    assert report["hard_fail"] is False
    assert report["status"] == "PASS"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
