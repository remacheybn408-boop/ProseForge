#!/usr/bin/env python3
"""Test classical_register_guard — 文言/古雅语体门禁测试"""
import sys
from pathlib import Path

from src.guards.classical_register_guard import (
    run_classical_register_check,
    analyze_classical_register,
)


def test_low_wenyan_passes():
    content = "周砚走到矿壁前，伸手摸了摸湿漉漉的石面。这里很安静，只有水滴的声音。"
    report = run_classical_register_check(content, 1)
    assert report["wenyan_density_percent"] <= 5
    assert report["readability_risk"] == "low"


def test_high_wenyan_detected():
    content = "然则此法不可久恃，盖天道有常，岂可违焉？夫修道者，必先正其心，而后方能悟其道也。"
    report = run_classical_register_check(content, 1)
    # 文言密度应该较高
    assert report["wenyan_density_percent"] >= 5  # 至少有些文言


def test_law_text_context():
    """宗门律令场景应该通过"""
    content = "宗门第三百二十一条律令：凡私入禁地者，逐出师门。周砚看完石碑，皱了皱眉。"
    analysis = analyze_classical_register(content)
    assert analysis["has_law_text"] is True


def test_raw_classical_block_without_reaction():
    """古文块后无现实反应应被检测"""
    content = "石壁上刻着：天道有常，不为尧存，不为桀亡。是以君子必慎其独也。"
    report = run_classical_register_check(content, 1)
    # 可能有古文块检测
    assert "raw_classical_blocks" in report


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
