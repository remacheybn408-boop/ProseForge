import json

import pytest

from src.pipeline import guard_orchestrator
from src.pipeline import ingest as ingest_module
from src.pipeline.post import _post_run_orchestrator


def test_guard_failure_is_blocking_and_never_fail_open(tmp_path, monkeypatch):
    def failed_run(*args, **kwargs):
        return {
            "status": "FAIL",
            "blocked_by": ["continuity_guard"],
            "failed_guards": ["continuity_guard"],
            "fail_count": 1,
            "executed_guards": ["continuity_guard"],
            "warnings": [],
            "warning_count": 0,
        }

    monkeypatch.setattr(guard_orchestrator, "run_orchestrated", failed_run)

    report = _post_run_orchestrator(
        "chapter text",
        1,
        "standard",
        {},
        tmp_path,
        "previous",
        {},
        {},
    )

    assert report["status"] == "BLOCK"
    assert report["can_ingest"] is False
    assert report["blocked_by"] == ["continuity_guard"]

    saved = json.loads(
        (tmp_path / "chapter_001_orchestrator_report.json").read_text(encoding="utf-8")
    )
    assert saved["can_ingest"] is False


def test_guard_crash_is_blocking(tmp_path, monkeypatch):
    def crashed_run(*args, **kwargs):
        raise RuntimeError("guard unavailable")

    monkeypatch.setattr(guard_orchestrator, "run_orchestrated", crashed_run)

    report = _post_run_orchestrator(
        "chapter text",
        1,
        "standard",
        {},
        tmp_path,
        "previous",
        {},
        {},
    )

    assert report["status"] == "ERROR"
    assert report["can_ingest"] is False
    assert report["errors"]

