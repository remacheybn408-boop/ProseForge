"""
test_pre_helpers.py — CODE_REVIEW #10

run_pre 拆出的可独立测试小函数的针对性单测。随增量抽取逐步补充。
"""
import sqlite3
import types

from src.pipeline.pre import (
    _pre_load_genre,
    _pre_write_context_pack,
    _pre_print_constraints,
)


def _novels_cur(genre_value):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE novels(id INTEGER PRIMARY KEY, genre TEXT)")
    conn.execute("INSERT INTO novels(id, genre) VALUES(1, ?)", (genre_value,))
    return conn.cursor()


def test_pre_load_genre_returns_value():
    cur = _novels_cur("xianxia")
    assert _pre_load_genre(cur, 1, []) == "xianxia"


def test_pre_load_genre_empty_when_null():
    cur = _novels_cur(None)
    assert _pre_load_genre(cur, 1, []) == ""


def test_pre_load_genre_missing_row_returns_empty():
    cur = _novels_cur("scifi")
    assert _pre_load_genre(cur, 999, []) == ""  # 无此 novel_id


def test_pre_load_genre_swallows_sql_error_and_logs():
    conn = sqlite3.connect(":memory:")  # 无 novels 表 → OperationalError
    log = []
    assert _pre_load_genre(conn.cursor(), 1, log) == ""
    assert any("genre lookup failed" in e for e in log)


def _fake_app(tmp_path):
    return types.SimpleNamespace(
        exports_root=tmp_path / "exports",
        volume_no=1,
        wc_default={"best_min": 2000, "best_max": 3000, "min": 1500, "max": 4000},
    )


def test_pre_write_context_pack_writes_file_with_skeleton(tmp_path):
    app = _fake_app(tmp_path)
    vol = {"planned_title": "山河卷"}
    ch_plan = {
        "planned_title": "初遇",
        "chapter_goal": "建立目标",
        "conflict_point": "门派纷争",
        "ending_hook_direction": "悬念收束",
    }
    pack_path = _pre_write_context_pack(app, 3, vol, ch_plan)
    assert pack_path.exists()
    text = pack_path.read_text(encoding="utf-8")
    assert "写作上下文包-第3章" in text
    assert "2000-3000" in text          # best range
    assert "标题骨架" in text and "初遇" in text


def test_pre_write_context_pack_no_skeleton_when_ch_plan_none(tmp_path):
    app = _fake_app(tmp_path)
    pack_path = _pre_write_context_pack(app, 1, None, None)
    assert pack_path.exists()
    text = pack_path.read_text(encoding="utf-8")
    assert "写作上下文包-第1章" in text
    assert "标题骨架" not in text        # ch_plan 为空 → 无骨架段


def test_pre_print_constraints_maps_thresholds_and_pacing(capsys):
    preset = {
        "water_density_min": 60,
        "conflict_pressure_min": 55,
        "pacing": {"focus_deltas": ["conflict_delta", "hook_delta"]},
    }
    _pre_print_constraints("xianxia", preset)
    out = capsys.readouterr().out
    assert "写作约束 [xianxia]" in out
    assert "注水阈值=60" in out and "冲突压力=55" in out
    assert "冲突 → 钩子" in out          # focus_deltas 标签映射


def test_pre_print_constraints_empty_preset_prints_nothing(capsys):
    _pre_print_constraints("xianxia", {})
    assert capsys.readouterr().out == ""   # 空 preset → 整块跳过
