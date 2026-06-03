#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent Run Guard — v0.3.1 Quality Guard Release

检查 chapter_run_report.json 的全部质量门禁。
所有硬门禁必须 true，否则 FAILED_NOVEL_WRITE_GUARD。

用法：
python scripts/agent_run_guard.py path/to/chapter_run_report.json
"""

import json
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"FAILED_NOVEL_WRITE_GUARD: {message}")
    sys.exit(1)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: python scripts/agent_run_guard.py path/to/chapter_run_report.json")

    report_path = Path(sys.argv[1])
    if not report_path.exists():
        fail(f"report not found: {report_path}")

    try:
        d = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json: {exc}")

    # ── 模式与 skill ──
    if d.get("mode") != "NOVEL_WRITE_MODE":
        fail("mode must be NOVEL_WRITE_MODE")
    if d.get("required_skill") != "novel-factory":
        fail("required_skill must be novel-factory")
    if d.get("skill_called") is not True:
        fail("skill_called must be true")

    # ── 前置 ──
    if d.get("pre_done") is not True:
        fail("pre_done must be true")
    if d.get("task_card_done") is not True:
        fail("task_card_done must be true")

    # ── 字数 ──
    length_mode = d.get("length_mode", "standard_chapter")
    chapter_wc = int(d.get("word_count", d.get("assembled_word_count", 0)))
    allow_short = bool(d.get("allow_short_chapter", False))
    chapter_type = d.get("chapter_type", "normal")

    if length_mode in ("authorized_short_chapter", "fragment_draft", "micro_scene", "outline_sample"):
        if not allow_short:
            fail("allow_short_chapter must be true for short/fragment modes")
        if chapter_wc < 300:
            fail(f"word_count {chapter_wc} below 300 for short chapter")
        if chapter_wc > 1000:
            fail(f"word_count {chapter_wc} exceeds 1000 for short chapter")
    else:
        if chapter_wc < 1300 and not allow_short:
            fail(f"word_count {chapter_wc} below 1300 minimum")
        if length_mode in ("standard_chapter", "fixed_budget_chapter"):
            if chapter_wc > 3300:
                pass  # warning only
        elif length_mode == "key_chapter":
            if chapter_wc > 4200:
                fail(f"word_count {chapter_wc} exceeds 4200 for key_chapter")
        elif length_mode == "climax_chapter":
            if chapter_wc > 5500:
                fail(f"word_count {chapter_wc} exceeds 5500 for climax_chapter")

    # ── Chunked writing ──
    write_mode = d.get("write_mode", "")
    if write_mode == "chunked":
        chunk_count = int(d.get("chunk_count", 0))
        if chunk_count < 4 and chapter_wc < 1300 and not allow_short:
            fail(f"chunk_count {chunk_count} < 4 with word_count {chapter_wc} < 1300")
        if d.get("chunk_gate_passed") is not True:
            fail("chunk_gate_passed must be true")
        chunk_wcs = d.get("chunk_word_counts", [])
        if not chunk_wcs and chunk_count > 0:
            fail("chunk_word_counts must not be empty when chunk_count > 0")

    # ── 门禁 ──
    if d.get("continuity_gate") is not True:
        fail("continuity_gate must be true")

    if d.get("hallucination_gate_passed") is not True:
        fail("hallucination_gate_passed must be true")
    allow_unsupported = bool(d.get("allow_unsupported_claims", False))
    if int(d.get("unsupported_claims_count", 0)) > 0 and not allow_unsupported:
        fail("unsupported_claims_count > 0")
    if int(d.get("contradictions_count", 0)) > 0:
        fail("contradictions_count > 0")
    if int(d.get("blocked_items_count", 0)) > 0:
        fail("blocked_items_count > 0")

    if d.get("scene_quality_gate") is not True:
        fail("scene_quality_gate must be true")
    if d.get("anti_ai_style_gate") is not True:
        fail("anti_ai_style_gate must be true")

    # ── 反水文 ──
    if d.get("padding_detected") is True:
        fail("padding_detected must be false")

    # ── 入库 ──
    if d.get("ingest_done") is not True:
        fail("ingest_done must be true")
    if d.get("next_allowed") is not True:
        fail("next_allowed must be true")

    # ── continuity evidence ──
    chapter_no = int(d.get("chapter_no", 0))
    if chapter_no > 1:
        if d.get("previous_tail_used") is not True:
            fail("previous_tail_used must be true for non-first chapter")
        if d.get("previous_chapter_link_passed") is not True:
            fail("previous_chapter_link_passed must be true")
        if float(d.get("continuity_evidence_score", 0)) < 0.8:
            fail("continuity_evidence_score below 0.8")
        if int(d.get("missing_hooks_count", 0)) > 0:
            fail("missing_hooks_count > 0")
        if int(d.get("forgotten_states_count", 0)) > 0:
            fail("forgotten_states_count > 0")

    # ── context usage ──
    if d.get("recent_summaries_used") is not True:
        fail("recent_summaries_used must be true")
    if d.get("character_states_used") is not True:
        fail("character_states_used must be true")
    if d.get("plot_threads_used") is not True:
        fail("plot_threads_used must be true")
    if d.get("reader_promises_used") is not True:
        fail("reader_promises_used must be true")
    if d.get("volume_context_used") is not True:
        fail("volume_context_used must be true")

    # ── padding evidence ──
    padding_score = int(d.get("padding_score", 0))
    padding_level = d.get("padding_level", "none")
    if padding_score > 60:
        fail(f"padding_score {padding_score} > 60")
    if padding_level == "fail":
        fail("padding_level is 'fail'")
    if not d.get("padding_report_path"):
        fail("padding_report_path missing")
    if not d.get("scene_delta_report_path"):
        fail("scene_delta_report_path missing")
    effective_scenes = int(d.get("effective_scene_delta_count", 0))
    if effective_scenes < 3 and not bool(d.get("allow_short_chapter", False)):
        fail(f"effective_scene_delta_count {effective_scenes} < 3")

    # ── canon evidence ──
    if not d.get("canon_evidence_map_path"):
        fail("canon_evidence_map_path missing")
    if float(d.get("evidence_coverage", 0)) < 0.95:
        fail("evidence_coverage below 0.95")
    if int(d.get("hard_claims_without_source", 0)) > 0:
        fail("hard_claims_without_source > 0")

    # ── volume bridge ──
    volume_no = int(d.get("volume_no", 1))
    if chapter_no > 1 and volume_no > 1:
        if "volume_bridge_report_used" in d and d.get("volume_bridge_report_used") is not True:
            fail("volume_bridge_report_used must be true for non-first volume")

    # ── execution proof ──
    if not d.get("execution_receipt_path"):
        fail("execution_receipt_path missing")
    if d.get("execution_receipt_verified") is not True:
        fail("execution_receipt_verified must be true")

    # ── v0.4.5: guard_summary check ──
    guard_summary_path = d.get("guard_summary_path", "")
    if not guard_summary_path:
        fail("guard_summary_path missing — guard_registry not executed")
    gs_path = Path(guard_summary_path)
    if not gs_path.exists():
        fail(f"guard_summary not found: {guard_summary_path}")
    try:
        gs = json.loads(gs_path.read_text(encoding="utf-8"))
        if gs.get("overall_status") == "FAIL":
            fail("guard_summary overall_status is FAIL")
    except Exception as e:
        fail(f"guard_summary parse error: {e}")

    print("PASS_NOVEL_WRITE_GUARD")


if __name__ == "__main__":
    main()
