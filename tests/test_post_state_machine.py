import types

import pytest

import src.pipeline.post as post_module
from src.pipeline.post import _post_resolve_state, _post_word_count_and_merge


def test_post_requires_pre_state(tmp_path):
    app = types.SimpleNamespace(state_dir=tmp_path / "state")

    with pytest.raises(RuntimeError, match="pre"):
        _post_resolve_state(app, 1)

    assert not (app.state_dir / "chapter_001_state.json").exists()


def test_post_rejects_wrong_chapter_type(tmp_path):
    app = types.SimpleNamespace(state_dir=tmp_path / "state")
    app.state_dir.mkdir()
    (app.state_dir / "chapter_001_state.json").write_text(
        '{"pre_done": true, "allowed_to_write": true, "chapter_no": 1, "chapter_type": "key"}',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="chapter_type"):
        _post_resolve_state(app, 1, chapter_type="normal")


def test_merge_failure_restores_both_source_files(tmp_path, monkeypatch):
    app = types.SimpleNamespace(
        tmp_root=tmp_path / "tmp",
        wc_rules={},
        wc_default={"min": 5, "max": 1000, "best_min": 10, "best_max": 900},
    )
    chapter_file = tmp_path / "chapter_001.txt"
    next_file = tmp_path / "chapter_002.txt"
    chapter_file.write_text("short-original", encoding="utf-8")
    next_file.write_text("next-original", encoding="utf-8")

    monkeypatch.setattr(
        post_module,
        "find_chapter_file_with_fallback",
        lambda chapter_no, app: next_file if chapter_no == 2 else chapter_file,
    )
    outcomes = iter([(False, 2, 5), (False, 4, 10)])
    monkeypatch.setattr(post_module, "word_count_gate", lambda *args, **kwargs: next(outcomes))

    args = types.SimpleNamespace(merge_if_short=True)
    with pytest.raises(RuntimeError, match="不足"):
        _post_word_count_and_merge(app, args, "short-original", 1, "normal", None, chapter_file)

    assert chapter_file.read_text(encoding="utf-8") == "short-original"
    assert next_file.read_text(encoding="utf-8") == "next-original"
    assert not list((app.tmp_root / "merge_runs").glob("*"))
