"""test_guard_entry_consistency.py — 确保 post/orchestrator 使用同一个 truth source"""

TEXT = """他从水里爬出来，胸口一阵肺痉挛，喉咙里全是铁锈味。
咳出来的水沫子挂在下巴上，右手还在抖。
"""


def test_registry_and_orchestrated_warning_count_consistent():
    """run_standard_guards and run_orchestrated must agree on warn/fail counts."""
    from scripts.guard_registry import run_standard_guards, run_orchestrated
    summary = run_standard_guards(TEXT, chapter_no=1, mode="standard")
    legacy = run_orchestrated(TEXT, chapter_no=1, mode="standard")
    assert legacy["warning_count"] == summary.warn_count, (
        f"warning_count mismatch: orchestrated={legacy['warning_count']} "
        f"vs registry={summary.warn_count}"
    )
    assert legacy["fail_count"] == summary.fail_count, (
        f"fail_count mismatch: orchestrated={legacy['fail_count']} "
        f"vs registry={summary.fail_count}"
    )


def test_guard_registry_validation_passes():
    """validate_guard_registry must report all 17 guards OK."""
    from scripts.guard_registry import validate_guard_registry
    result = validate_guard_registry()
    assert result["ok"], f"Registry validation failed: {result['errors']}"
    assert result["registered_count"] == 27  # 22 core + 5 v0.7.2 (emotional, opening, sensory, pacing, pov)
