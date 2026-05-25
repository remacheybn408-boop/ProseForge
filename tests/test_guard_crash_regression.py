"""test_guard_crash_regression.py — 确保所有 standard mode guards 不 crash"""

import sys
sys.path.insert(0, "scripts")

from guard_registry import run_standard_guards

SAMPLE = """他从水里爬出来，胸口一阵肺痉挛，喉咙里全是铁锈味。
咳出来的水沫子挂在下巴上，右手还在抖。
测试角色看了他一眼：\"规矩在这。\"
"""


def test_standard_guards_do_not_crash():
    """All standard mode guards execute without crash or *_ERROR findings."""
    summary = run_standard_guards(SAMPLE, chapter_no=1, mode="standard")
    for result in summary.results:
        assert not result.error, f"{result.guard} crashed: {result.error}"
        assert not any(
            "Guard crashed" in f.message for f in result.findings
        ), f"{result.guard} reports crash"
        assert not any(
            f.code.endswith("_ERROR") for f in result.findings
        ), f"{result.guard} has _ERROR finding: {[f.code for f in result.findings]}"


def test_continuity_evidence_no_str_int_error():
    """continuity_evidence_guard must handle chapter_no as int correctly."""
    from continuity_evidence_guard import run_continuity_evidence_check
    report = run_continuity_evidence_check(2, SAMPLE, prev_chapter_no=1)
    assert report["final_decision"] in ("PASS", "FAIL")
    # Must not contain str-int error markers
    assert "operand type" not in str(report)
