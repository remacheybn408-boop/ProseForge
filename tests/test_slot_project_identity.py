import json
import shutil
from pathlib import Path

from src.db.slot_manager import SlotManager


def test_new_slot_persists_project_slug(tmp_path):
    (tmp_path / "database").mkdir()
    shutil.copy(Path(__file__).parents[1] / "database" / "schema.sql", tmp_path / "database" / "schema.sql")
    manager = SlotManager(tmp_path)

    manager.create_slot(
        "slot_alpha",
        ensure_registry=True,
        name="Alpha",
        description="Alpha",
        slug="novel_alpha",
    )

    project = json.loads(
        (tmp_path / "workspace" / "slot_alpha" / "project.json").read_text(
            encoding="utf-8"
        )
    )
    assert project["slug"] == "novel_alpha"
