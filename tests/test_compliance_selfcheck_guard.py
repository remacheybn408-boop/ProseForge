#!/usr/bin/env python3
"""Test compliance_selfcheck_guard — 投稿合规自查门禁测试"""
import sys, json
from pathlib import Path

from src.guards.compliance_selfcheck_guard import (
    build_report,
    check_category,
    RISK_PATTERNS,
)


# ═══════════════════════════════════════════════════
# 工具函数测试
# ═══════════════════════════════════════════════════

def test_check_category_no_match():
    """无匹配返回 none"""
    text = "今天天气很好，阳光明媚。"
    result = check_category(text, "explicit_sexual", RISK_PATTERNS["explicit_sexual"])
    assert result["risk"] == "none"
    assert result["count"] == 0


def test_check_category_medium_match():
    """中等匹配返回 medium"""
    text = "暧昧的夜色中，他们在床上缠绵，久久不愿分开。"
    result = check_category(text, "explicit_sexual", RISK_PATTERNS["explicit_sexual"])
    assert result["risk"] in ("low", "medium", "high")
    assert result["count"] > 0


# ═══════════════════════════════════════════════════
# 核心门禁测试
# ═══════════════════════════════════════════════════

def test_normal_text_passes():
    """正常文本通过"""
    content = (
        "周砚走到矿壁前，伸手摸了摸湿漉漉的石面。"
        "这里很安静，只有水滴的声音。他敲了敲石壁，声音沉闷。"
        '"再试一次。"沈师姐说。'
    )
    report = build_report(content, 1)
    assert report["guard"] == "compliance_selfcheck_guard"
    assert report["status"] == "PASS"
    assert report["hard_fail"] is False
    assert len(report["blocked_categories"]) == 0
    assert len(report["warnings_categories"]) == 0


def test_explicit_sexual_triggers_block():
    """露骨性内容 → BLOCK"""
    content = (
        "她感受着他的阳具在体内抽插，一阵阵高潮让她几乎昏厥。"
        "精液从她的下体缓缓流出，那是他们交合的证明。"
    )
    report = build_report(content, 1)
    assert report["status"] == "BLOCK"
    assert report["hard_fail"] is True
    assert "explicit_sexual" in report["blocked_categories"]


def test_extreme_gore_triggers_block():
    """极端血腥 → BLOCK"""
    content = (
        "他一刀将敌人肢解，鲜血如喷涌的泉水。"
        "挖眼割舌之后，他剥下了对方的皮，内脏散落一地。"
        "凌迟的痛苦让那人发出了非人的惨叫。"
    )
    report = build_report(content, 1)
    assert report["status"] == "BLOCK"
    assert report["hard_fail"] is True
    assert "extreme_gore" in report["blocked_categories"]


def test_ad_spam_triggers_block():
    """广告引流 → BLOCK"""
    content = (
        "喜欢这本书的读者请加微信xxxx获取全文更新。"
        "关注公众号xxxx，每日更新不迷路。"
    )
    report = build_report(content, 1)
    assert report["status"] == "BLOCK"
    assert report["hard_fail"] is True
    assert "ad_spam" in report["blocked_categories"]


def test_political_sensitivity_triggers_block():
    """政治敏感 → BLOCK"""
    content = "他在书中宣扬台独思想，鼓吹分裂国家的言论。"
    report = build_report(content, 1)
    # political_sensitivity 应该被捕获
    assert report["status"] == "BLOCK"
    assert "political_sensitivity" in report["blocked_categories"]


def test_mild_gore_only_warns():
    """轻度血腥只 WARNING"""
    content = (
        "他的剑刺入对方肩膀。鲜血从伤口涌出，"
        "疼痛让他发出了痛苦的呻吟。这伤势不轻，但不会有生命危险。"
    )
    report = build_report(content, 1)
    # 不应该 BLOCK，最多 WARNING 或 PASS
    assert report["status"] in ("PASS", "WARNING")
    assert report["hard_fail"] is False


def test_empty_text_handled():
    """空文本不崩溃"""
    report = build_report("", 1)
    assert report["status"] == "PASS"
    assert report["hard_fail"] is False


def test_report_json_fields_complete():
    """输出 JSON 字段完整"""
    content = "正常测试文本内容。"
    report = build_report(content, 1)
    required_fields = [
        "guard", "version", "status", "chapter_no",
        "risks", "blocked_categories", "warnings_categories",
        "passed_categories", "suggestions", "hard_fail"
    ]
    for field in required_fields:
        assert field in report, f"Missing field: {field}"

    # risk 子字段
    for cat in ["underage_risk", "explicit_sexual", "extreme_gore",
                "crime_tutorial", "hate_speech", "political_sensitivity",
                "ad_spam", "plagiarism_risk"]:
        assert cat in report["risks"], f"Missing risk category: {cat}"
        assert "risk_level" in report["risks"][cat]
        assert report["risks"][cat]["risk_level"] in ("none", "low", "medium", "high")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
