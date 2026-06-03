"""
test_agent_run_guard.py — Quality Guard 测试 (V5: chapter_type不强制下限)
"""
import pytest, json, tempfile, sys, os, io, contextlib, importlib
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

GUARD_SCRIPT = Path(__file__).parent.parent / "scripts" / "agent_run_guard.py"


def _run_guard(report_dict):
    """Run agent_run_guard in-process.

    The old version spawned a Python subprocess for every assertion. On some
    CI/local shells that became slow or flaky because all cases reused the same
    temporary guard_summary path. Running the guard directly is deterministic
    and keeps the same public behavior: returncode + stdout.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(report_dict, f)
        tmp = f.name

    gs_path = report_dict.get("guard_summary_path", "")
    if gs_path:
        gs_dir = os.path.dirname(gs_path)
        if gs_dir:
            os.makedirs(gs_dir, exist_ok=True)
        with open(gs_path, 'w', encoding='utf-8') as gs:
            json.dump({"overall_status": "PASS", "chapter_no": report_dict.get("chapter_no", 1)}, gs)

    old_argv = sys.argv[:]
    buf = io.StringIO()
    rc = 0
    try:
        sys.argv = [str(GUARD_SCRIPT), tmp]
        guard_mod = importlib.import_module("agent_run_guard")
        with contextlib.redirect_stdout(buf):
            try:
                guard_mod.main()
                rc = 0
            except SystemExit as e:
                rc = int(e.code or 0)
    except Exception as e:
        pytest.fail(f"agent_run_guard failed in-process: {e}")
    finally:
        sys.argv = old_argv
        Path(tmp).unlink(missing_ok=True)
        if gs_path and os.path.exists(gs_path):
            os.remove(gs_path)
    return rc, buf.getvalue()

def _valid_report(**overrides):
    base = {
        "mode": "NOVEL_WRITE_MODE", "required_skill": "novel-factory", "skill_called": True,
        "length_mode": "standard_chapter", "chapter_type": "normal",
        "write_mode": "chunked", "chunk_count": 4, "chunk_word_counts": [500,620,680,600],
        "chunk_gate_passed": True, "chapter_no": 1, "title": "test",
        "assembled_word_count": 2400, "word_count": 2400,
        "chapter_word_count_gate": True, "word_count_gate": True, "allow_short_chapter": False,
        "pre_done": True, "task_card_done": True, "continuity_gate": True,
        "hallucination_gate_passed": True, "unsupported_claims_count": 0,
        "contradictions_count": 0, "blocked_items_count": 0,
        "scene_quality_gate": True, "anti_ai_style_gate": True, "padding_detected": False,
        "ingest_done": True, "next_allowed": True,
        "previous_tail_used": True, "previous_chapter_link_passed": True,
        "continuity_evidence_score": 1.0, "missing_hooks_count": 0, "forgotten_states_count": 0,
        "recent_summaries_used": True, "character_states_used": True,
        "plot_threads_used": True, "reader_promises_used": True, "volume_context_used": True,
        "padding_score": 0, "padding_level": "none",
        "padding_report_path": "exports/demo/reports/ch_001_padding.json",
        "scene_delta_report_path": "exports/demo/reports/ch_001_scene_delta.json",
        "effective_scene_delta_count": 4,
        "canon_evidence_map_path": "exports/demo/evidence/ch_001_canon.json",
        "evidence_coverage": 1.0, "hard_claims_without_source": 0,
        "execution_receipt_path": "exports/demo/receipts/ch_001_receipt.json",
        "execution_receipt_verified": True, "volume_no": 1,
        "guard_summary_path": "exports/demo/reports/ch_001_guard_summary.json"
    }
    base.update(overrides)
    return base


class TestGuardPass:
    def test_normal_2400_passes(self):
        rc, out = _run_guard(_valid_report(word_count=2400, assembled_word_count=2400))
        assert rc == 0

    def test_key_2000_passes(self):
        """Key chapter at 2000 should pass — not forced to 3300"""
        rc, out = _run_guard(_valid_report(length_mode="key_chapter", chapter_type="key", word_count=2000))
        assert rc == 0

    def test_climax_2800_passes(self):
        """Climax at 2800 should pass — not forced to 4200"""
        rc, out = _run_guard(_valid_report(length_mode="climax_chapter", chapter_type="climax", word_count=2800))
        assert rc == 0


class TestGuardFail:
    def test_normal_1500_passes(self):
        """1500 should pass — min is now 1300"""
        rc, out = _run_guard(_valid_report(word_count=1500, assembled_word_count=1500, chapter_word_count_gate=True, word_count_gate=True))
        assert rc == 0

    def test_normal_1200_fails(self):
        """1200 should fail — below 1300 minimum"""
        rc, out = _run_guard(_valid_report(word_count=1200, assembled_word_count=1200, chapter_word_count_gate=False, word_count_gate=False))
        assert rc != 0

    def test_key_4300_oversize_fails(self):
        rc, out = _run_guard(_valid_report(length_mode="key_chapter", chapter_type="key", word_count=4300))
        assert rc != 0

    def test_hallucination_fail_blocks(self):
        rc, out = _run_guard(_valid_report(hallucination_gate_passed=False))
        assert rc != 0

    def test_padding_detected_blocks(self):
        rc, out = _run_guard(_valid_report(padding_detected=True))
        assert rc != 0

    # ── New guard checks ──

    def test_previous_tail_used_false_fails(self):
        rc, out = _run_guard(_valid_report(chapter_no=2, previous_tail_used=False))
        assert rc != 0

    def test_missing_hooks_fails(self):
        rc, out = _run_guard(_valid_report(chapter_no=2, missing_hooks_count=1))
        assert rc != 0

    def test_forgotten_states_fails(self):
        rc, out = _run_guard(_valid_report(chapter_no=2, forgotten_states_count=1))
        assert rc != 0

    def test_padding_score_exceeds_fails(self):
        rc, out = _run_guard(_valid_report(padding_score=65))
        assert rc != 0

    def test_padding_level_fail_fails(self):
        rc, out = _run_guard(_valid_report(padding_level="fail"))
        assert rc != 0

    def test_evidence_coverage_low_fails(self):
        rc, out = _run_guard(_valid_report(evidence_coverage=0.90))
        assert rc != 0

    def test_hard_claims_without_source_fails(self):
        rc, out = _run_guard(_valid_report(hard_claims_without_source=1))
        assert rc != 0

    def test_execution_receipt_verified_false_fails(self):
        rc, out = _run_guard(_valid_report(execution_receipt_verified=False))
        assert rc != 0
