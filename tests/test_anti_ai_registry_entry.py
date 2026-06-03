"""test_anti_ai_registry_entry.py — 确认 anti_ai_guard 从 registry 正确调用到 anti_ai_patterns"""

import sys
sys.path.insert(0, "scripts")

from guard_registry import run_single_guard


def test_anti_ai_registry_entry_uses_patterns_module():
    """anti_ai_guard via registry must not crash and return valid GuardResult."""
    content = "三块石头不是不同材质，而是对灵气场的耦合程度不同。石粉从指缝里落下来。"
    result = run_single_guard("anti_ai_guard", content, chapter_no=2)
    assert result is not None, "run_single_guard returned None"
    assert not result.error, f"anti_ai crashed: {result.error}"
    assert result.guard == "anti_ai_guard"


def test_anti_ai_not_a_b_with_evidence_no_warn():
    """Single 不是...而是 with physical evidence should not WARN."""
    from src.guards.anti_ai_patterns import check_anti_ai
    content = "三块石头不是不同材质，而是对灵气场的耦合程度不同。石粉从指缝里落下来。"
    score, findings = check_anti_ai(content)
    # Should have findings but low confidence (evidence present)
    high_conf = [f for f in findings if f.get("confidence", 0) >= 0.5]
    assert len(high_conf) == 0, f"Unexpected high-confidence AI flags: {high_conf}"
