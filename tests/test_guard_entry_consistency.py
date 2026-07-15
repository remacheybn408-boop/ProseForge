"""test_guard_entry_consistency.py — 确保 post/orchestrator 使用同一个 truth source"""

TEXT = """他从水里爬出来，胸口一阵肺痉挛，喉咙里全是铁锈味。
咳出来的水沫子挂在下巴上，右手还在抖。
"""


def test_registry_and_orchestrated_warning_count_consistent():
    """run_standard_guards and run_orchestrated must agree on warn/fail counts."""
    from src.guards.guard_registry import run_standard_guards, run_orchestrated
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
    """validate_guard_registry must report all v0.8.0 guards OK (10 total: L1×4 + L2×5 + L3×1)."""
    from src.guards.guard_registry import validate_guard_registry
    result = validate_guard_registry()
    assert result["ok"], f"Registry validation failed: {result['errors']}"
    assert result["registered_count"] == 10, (
        f"expected 10 guards (4 L1 + 5 L2 aggregators + 1 L3); got {result['registered_count']}"
    )


def test_legacy_entry_preserves_chapter_type(monkeypatch):
    import src.guards.guard_registry as registry

    captured = {}

    class FakeSummary:
        version = "test"
        executed_guards = []
        skipped_guards = []
        blocked_by = []
        crashed_guards = []
        warn_count = 0
        fail_count = 0
        overall_status = "PASS"
        results = []

        @staticmethod
        def get_warnings():
            return []

    def fake_run_standard_guards(**kwargs):
        captured["chapter_type"] = kwargs["chapter_type"]
        return FakeSummary()

    monkeypatch.setattr(registry, "run_standard_guards", fake_run_standard_guards)

    registry.run_orchestrated("text", chapter_no=1, chapter_type="climax")

    assert captured["chapter_type"] == "climax"
