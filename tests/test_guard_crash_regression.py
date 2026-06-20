"""test_guard_crash_regression.py — 确保所有 standard mode guards 不 crash"""

from src.guards.guard_registry import run_standard_guards

SAMPLE = """他从水里爬出来，胸口一阵肺痉挛，喉咙里全是铁锈味。
咳出来的水沫子挂在下巴上，右手还在抖。
测试角色看了他一眼：\"规矩在这。\"
"""


def test_standard_guards_do_not_crash():
    """All standard mode guards execute without crash or *_ERROR findings."""
    summary = run_standard_guards(SAMPLE, chapter_no=1, mode="standard")
    assert "prose_authenticity_guard" in summary.executed_guards
    for result in summary.results:
        assert not result.error, f"{result.guard} crashed: {result.error}"
        assert not any(
            "Guard crashed" in f.message for f in result.findings
        ), f"{result.guard} reports crash"
        assert not any(
        f.code.endswith("_ERROR") for f in result.findings
        ), f"{result.guard} has _ERROR finding: {[f.code for f in result.findings]}"


def test_standard_and_submission_guard_sets_are_intentional():
    """standard includes AI-authenticity checks; compliance remains submission-only."""
    from src.guards.guard_registry import MODE_GUARDS

    assert "prose_authenticity_guard" in MODE_GUARDS["standard"]
    assert "compliance_selfcheck_guard" not in MODE_GUARDS["standard"]
    assert len(MODE_GUARDS["standard"]) == 9
    assert set(MODE_GUARDS["submission"]) == {
        "continuity_evidence_guard",
        "canon_evidence_guard",
        "hallucination_guard",
        "scene_delta_guard",
        "scene_grounding_guard",
        "narrative_rhythm_guard",
        "dialogue_quality_guard",
        "prose_authenticity_guard",
        "reader_engagement_guard",
        "compliance_selfcheck_guard",
    }


def test_continuity_evidence_no_str_int_error():
    """continuity_evidence_guard must handle chapter_no as int correctly."""
    from src.guards.continuity_evidence_guard import run_continuity_evidence_check
    report = run_continuity_evidence_check(2, SAMPLE, prev_chapter_no=1)
    assert report["final_decision"] in ("PASS", "FAIL")
    # Must not contain str-int error markers
    assert "operand type" not in str(report)
