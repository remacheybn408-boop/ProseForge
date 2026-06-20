from src.story import STORY_DIR, resolve_story_dir


def test_resolve_story_dir_prefers_active_slot_story(tmp_path):
    workspace = tmp_path / "workspace"
    slot_story = workspace / "slot_alpha" / STORY_DIR
    slot_story.mkdir(parents=True)
    (workspace / "registry.json").write_text('{"active_slot": "slot_alpha"}', encoding="utf-8")

    assert resolve_story_dir(tmp_path) == slot_story


def test_resolve_story_dir_falls_back_to_project_story(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "registry.json").write_text('{"active_slot": "slot_alpha"}', encoding="utf-8")

    assert resolve_story_dir(tmp_path) == tmp_path / STORY_DIR
