#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agent Run Guard

用途：
检查 Hermes Agent 的正文写作报告，确认它是否真的进入 NOVEL_WRITE_MODE，
是否声明调用 novel-factory skill，是否完成核心 pipeline 门禁。

用法：
python scripts/agent_run_guard.py path/to/chapter_run_report.json
"""

import json
import sys
from pathlib import Path


REQUIRED_TRUE_FIELDS = [
    "skill_called",
    "pre_done",
    "task_card_done",
    "word_count_gate",
    "continuity_gate",
    "scene_quality_gate",
    "anti_ai_style_gate",
    "ingest_done",
]

REQUIRED_KEYS = [
    "mode",
    "required_skill",
    "skill_called",
    "chapter_no",
    "word_count",
    "pre_done",
    "task_card_done",
    "word_count_gate",
    "continuity_gate",
    "scene_quality_gate",
    "anti_ai_style_gate",
    "ingest_done",
]


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
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid json: {exc}")

    for key in REQUIRED_KEYS:
        if key not in data:
            fail(f"missing key: {key}")

    if data["mode"] != "NOVEL_WRITE_MODE":
        fail("mode must be NOVEL_WRITE_MODE")

    if data["required_skill"] != "novel-factory":
        fail("required_skill must be novel-factory")

    for key in REQUIRED_TRUE_FIELDS:
        if data.get(key) is not True:
            fail(f"{key} must be true")

    word_count = int(data.get("word_count", 0))
    allow_short = bool(data.get("allow_short_chapter", False))

    if word_count < 3300 and not allow_short:
        fail("word_count below 3300 and allow_short_chapter is false")

    print("PASS_NOVEL_WRITE_GUARD")


if __name__ == "__main__":
    main()
