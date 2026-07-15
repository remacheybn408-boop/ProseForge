import json

import pytest

from src.runtime import build_pipeline_context


def test_pipeline_context_can_bind_explicit_slot_without_active_slot(tmp_path):
    workspace = tmp_path / "workspace"
    slot = workspace / "novel_a"
    slot.mkdir(parents=True)
    (workspace / "registry.json").write_text(
        json.dumps({"active_slot": "novel_b", "slots": ["novel_a", "novel_b"]}),
        encoding="utf-8",
    )
    (slot / "project.json").write_text(
        json.dumps({"slug": "novel_a", "title": "A"}), encoding="utf-8"
    )

    context = build_pipeline_context(
        project_root=tmp_path,
        slot_id="novel_a",
        novel_slug="novel_a",
    )

    assert context.active_slot == "novel_a"
    assert context.db_path == slot / "novel.db"


def test_pipeline_context_rejects_unknown_explicit_slot(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        build_pipeline_context(
            project_root=tmp_path,
            slot_id="missing",
            novel_slug="missing",
        )
