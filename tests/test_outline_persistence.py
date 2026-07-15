import json

from src.outline.outline_manager import OutlineManager
from src.db.registry import Registry


def test_outline_manager_uses_canonical_registry(tmp_path):
    registry = Registry(tmp_path)
    registry.add_slot("novel_a", "Novel A")
    registry.set_active_slot("novel_a")

    manager = OutlineManager(tmp_path)

    assert manager._get_registry()["active_slot"] == "novel_a"
    assert manager._get_active_slot() == "novel_a"


def test_outline_metadata_writes_are_atomic(tmp_path):
    registry = Registry(tmp_path)
    registry.add_slot("novel_a", "Novel A")
    registry.set_active_slot("novel_a")
    manager = OutlineManager(tmp_path)

    manager._save_project_json({"active_outline": "outline_1"})
    manager._write_outline_file("outline_1", {"id": "outline_1", "title": "Test"})

    project_file = tmp_path / "workspace" / "novel_a" / "project.json"
    outline_file = tmp_path / "workspace" / "novel_a" / "outlines" / "outline_1.json"
    assert json.loads(project_file.read_text(encoding="utf-8"))["active_outline"] == "outline_1"
    assert json.loads(outline_file.read_text(encoding="utf-8"))["id"] == "outline_1"
    assert not list((tmp_path / "workspace").rglob("*.tmp"))


def test_outline_structure_counts_multiple_volumes_and_chapters(tmp_path):
    manager = OutlineManager(tmp_path)
    chapters, volumes = manager._count_outline_structure(
        "第1卷 起点\n第1章 开始\n第2章 冲突\n\n第2卷 转折\n第3章 代价\n"
    )

    assert chapters == 3
    assert volumes == 2
