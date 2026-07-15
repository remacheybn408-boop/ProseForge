import json
import sqlite3

import pytest

from src.runtime import build_pipeline_context


def test_context_rejects_slug_that_does_not_match_active_slot(tmp_path):
    workspace = tmp_path / "workspace"
    slot = workspace / "slot_alpha"
    slot.mkdir(parents=True)
    (workspace / "registry.json").write_text(
        json.dumps({"active_slot": "slot_alpha", "slots": ["slot_alpha"]}),
        encoding="utf-8",
    )
    (slot / "project.json").write_text(
        json.dumps({"slug": "novel_alpha"}), encoding="utf-8"
    )
    sqlite3.connect(slot / "novel.db").close()

    with pytest.raises(ValueError, match="does not match active project"):
        build_pipeline_context(novel_slug="novel_beta", project_root=tmp_path)


def test_context_uses_matching_active_slot(tmp_path):
    workspace = tmp_path / "workspace"
    slot = workspace / "slot_alpha"
    slot.mkdir(parents=True)
    (workspace / "registry.json").write_text(
        json.dumps({"active_slot": "slot_alpha", "slots": ["slot_alpha"]}),
        encoding="utf-8",
    )
    (slot / "project.json").write_text(
        json.dumps({"slug": "novel_alpha"}), encoding="utf-8"
    )
    sqlite3.connect(slot / "novel.db").close()

    context = build_pipeline_context(novel_slug="novel_alpha", project_root=tmp_path)

    assert context.active_slot == "slot_alpha"
    assert context.db_path == slot / "novel.db"
