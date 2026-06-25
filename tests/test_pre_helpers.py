"""
test_pre_helpers.py — CODE_REVIEW #10

run_pre 拆出的可独立测试小函数的针对性单测。随增量抽取逐步补充。
"""
import sqlite3

from src.pipeline.pre import _pre_load_genre


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
