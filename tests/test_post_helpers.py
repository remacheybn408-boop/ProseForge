"""
test_post_helpers.py — CODE_REVIEW #10 (run_post 拆出的小函数单测)

随增量抽取逐步补充。
"""
import json
import sqlite3
import types

import pytest

from src.pipeline.post import (
    _post_resolve_state,
    _post_resolve_genre,
    _post_load_prev_brief,
    _post_word_count_and_merge,
)
from src.pipeline._base import write_json_atomic


# ── _post_resolve_state ──────────────────────────────────────────────
def _state_app(tmp_path):
    return types.SimpleNamespace(state_dir=tmp_path / "state")


def test_resolve_state_requires_pre_when_missing(tmp_path):
    app = _state_app(tmp_path)
    with pytest.raises(RuntimeError, match="pre"):
        _post_resolve_state(app, 1)
    return
    assert not (app.state_dir / "chapter_001_state.json").exists()
    assert state_path.exists()                         # 写盘


def test_resolve_state_reads_existing(tmp_path):
    app = _state_app(tmp_path)
    sp = app.state_dir / "chapter_002_state.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(sp, {"allowed_to_write": True, "pre_done": True, "chapter_no": 2,
                           "chapter_type": "normal", "genre": "scifi", "timestamp": "t0"})
    state, state_path = _post_resolve_state(app, 2)
    assert state["genre"] == "scifi"
    assert "_bootstrapped" not in state                # 走已存在分支


def test_resolve_state_raises_when_not_allowed(tmp_path):
    app = _state_app(tmp_path)
    sp = app.state_dir / "chapter_003_state.json"
    sp.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(sp, {"allowed_to_write": False})
    with pytest.raises(RuntimeError):
        _post_resolve_state(app, 3)


# ── _post_resolve_genre ──────────────────────────────────────────────
def _genre_app(tmp_path, slug, genre):
    db = tmp_path / "g.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE novels(slug TEXT, genre TEXT)")
    conn.execute("INSERT INTO novels(slug, genre) VALUES(?,?)", (slug, genre))
    conn.commit()
    conn.close()
    return types.SimpleNamespace(db_path=str(db), novel_slug=slug)


def test_resolve_genre_prefers_state(tmp_path):
    app = _genre_app(tmp_path, "s1", "fromdb")
    assert _post_resolve_genre(app, {"genre": "fromstate"}) == "fromstate"


def test_resolve_genre_falls_back_to_db(tmp_path):
    app = _genre_app(tmp_path, "s1", "fromdb")
    assert _post_resolve_genre(app, {"genre": ""}) == "fromdb"


def test_resolve_genre_empty_when_no_row(tmp_path):
    app = _genre_app(tmp_path, "s1", "fromdb")
    app.novel_slug = "missing"
    assert _post_resolve_genre(app, {}) == ""


# ── _post_load_prev_brief ────────────────────────────────────────────
def _exports_app(tmp_path):
    return types.SimpleNamespace(exports_root=tmp_path / "exports")


def test_load_prev_brief_missing_returns_defaults(tmp_path):
    app = _exports_app(tmp_path)
    prev_brief, prev_tail = _post_load_prev_brief(app, 5)
    assert prev_brief is None and prev_tail == ""


def test_load_prev_brief_reads_ending_state(tmp_path):
    app = _exports_app(tmp_path)
    bd = app.exports_root / "chapter_briefs"
    bd.mkdir(parents=True, exist_ok=True)
    (bd / "chapter_004_brief.json").write_text(
        json.dumps({"ending_state": "夜色降临"}), encoding="utf-8")
    prev_brief, prev_tail = _post_load_prev_brief(app, 5)   # 读第 4 章
    assert prev_brief["ending_state"] == "夜色降临"
    assert prev_tail == "夜色降临"


# ── _post_word_count_and_merge ───────────────────────────────────────
def _wc_app():
    return types.SimpleNamespace(
        wc_rules={},
        wc_default={"min": 5, "max": 1000, "best_min": 10, "best_max": 900},
    )


def test_word_count_pass_returns_content_and_count():
    app = _wc_app()
    args = types.SimpleNamespace(merge_if_short=False)
    content = "你好世界" * 10                    # 40 个中文字，过下限
    out_content, wc = _post_word_count_and_merge(app, args, content, 1, "normal", None, None)
    assert out_content == content
    assert wc == 40


def test_word_count_short_without_merge_raises():
    app = _wc_app()
    args = types.SimpleNamespace(merge_if_short=False)
    with pytest.raises(RuntimeError, match="short by"):
        _post_word_count_and_merge(app, args, "短", 1, "normal", None, None)
