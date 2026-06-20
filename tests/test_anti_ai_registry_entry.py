"""test_anti_ai_registry_entry.py

v0.8.0：anti_ai 子检测被并入 prose_authenticity_guard。本测试改为验证：
registry 跑 prose_authenticity_guard 时，anti_ai_guard 出现在 _guards_raw 里
且不报 crash。
"""

from src.guards.guard_registry import run_single_guard


def test_anti_ai_subcheck_runs_via_prose_authenticity():
    """prose_authenticity_guard via registry must include anti_ai sub-result without crashing."""
    content = "三块石头不是不同材质，而是对灵气场的耦合程度不同。石粉从指缝里落下来。"
    result = run_single_guard("prose_authenticity_guard", content, chapter_no=2)
    assert result is not None, "run_single_guard returned None"
    assert not result.error, f"prose_authenticity crashed: {result.error}"
    assert result.guard == "prose_authenticity_guard"

    sub_names = [s.get("guard") for s in (result.metrics.get("_guards_raw") or [])
                 if isinstance(s, dict)]
    assert "anti_ai_guard" in sub_names, (
        f"anti_ai_guard 未出现在 prose_authenticity 的子检测里：{sub_names}"
    )


def test_anti_ai_not_a_b_with_evidence_no_warn():
    """Single 不是...而是 with physical evidence should not WARN."""
    from src.guards.anti_ai_guard import check_anti_ai
    content = "三块石头不是不同材质，而是对灵气场的耦合程度不同。石粉从指缝里落下来。"
    score, findings = check_anti_ai(content)
    # Should have findings but low confidence (evidence present)
    high_conf = [f for f in findings if f.get("confidence", 0) >= 0.5]
    assert len(high_conf) == 0, f"Unexpected high-confidence AI flags: {high_conf}"
