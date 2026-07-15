import sqlite3

from src.pipeline.ingest import _get_hostile_relationships
from src.pipeline.task_card_builder import get_character_relations


def test_hostile_relationships_are_scoped_to_novel():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE character_relationships "
        "(novel_id INTEGER, char_a TEXT, char_b TEXT, relation_type TEXT)"
    )
    conn.executemany(
        "INSERT INTO character_relationships VALUES (?, ?, ?, ?)",
        [(1, "甲", "乙", "敌对"), (2, "丙", "丁", "敌对")],
    )

    assert _get_hostile_relationships(conn.cursor(), 1) == [("甲", "乙")]
    conn.close()


def test_task_card_relationships_are_scoped_to_novel():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        "CREATE TABLE character_relationships "
        "(novel_id INTEGER, char_a TEXT, char_b TEXT, relation_type TEXT)"
    )
    conn.executemany(
        "INSERT INTO character_relationships VALUES (?, ?, ?, ?)",
        [(1, "甲", "乙", "敌对"), (2, "丙", "丁", "盟友")],
    )

    assert get_character_relations(conn, 1) == [
        {"char_a": "甲", "char_b": "乙", "type": "敌对"}
    ]
    conn.close()
