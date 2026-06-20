import sqlite3
from pathlib import Path

from src.pipeline.task_card_builder import build_task_card, get_chapter_plan


def _prepare_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE novels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT DEFAULT ''
        );

        CREATE TABLE chapter_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            volume_no INTEGER NOT NULL,
            chapter_no INTEGER NOT NULL,
            planned_title TEXT DEFAULT '',
            chapter_goal TEXT DEFAULT '',
            conflict_point TEXT DEFAULT '',
            ending_hook_direction TEXT DEFAULT '',
            continuity_from_previous TEXT DEFAULT '',
            main_event TEXT DEFAULT '',
            character_focus TEXT DEFAULT '',
            must_include TEXT DEFAULT '',
            plot_threads_to_advance TEXT DEFAULT '',
            reader_promises_to_advance TEXT DEFAULT ''
        );

        CREATE TABLE chapters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            chapter_no INTEGER NOT NULL,
            content TEXT DEFAULT ''
        );

        CREATE TABLE chapter_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            chapter_id INTEGER NOT NULL,
            short_summary TEXT DEFAULT ''
        );

        CREATE TABLE writing_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            content TEXT DEFAULT '',
            rule_type TEXT DEFAULT '',
            status TEXT DEFAULT 'active'
        );

        CREATE TABLE plot_threads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            title TEXT DEFAULT '',
            status TEXT DEFAULT 'open'
        );

        CREATE TABLE reader_promises (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            novel_id INTEGER NOT NULL,
            promise_title TEXT DEFAULT '',
            status TEXT DEFAULT 'open'
        );
        """
    )

    conn.execute("INSERT INTO novels(slug, title) VALUES(?, ?)", ("demo_novel", "Demo Novel"))
    novel_id = conn.execute("SELECT id FROM novels WHERE slug = ?", ("demo_novel",)).fetchone()[0]

    conn.execute(
        """
        INSERT INTO chapter_plans(
            novel_id, volume_no, chapter_no, planned_title, chapter_goal, ending_hook_direction
        ) VALUES(?, ?, ?, ?, ?, ?)
        """,
        (novel_id, 1, 3, "Volume One Plan", "Goal for volume one", "Hook one"),
    )
    conn.execute(
        """
        INSERT INTO chapter_plans(
            novel_id, volume_no, chapter_no, planned_title, chapter_goal, ending_hook_direction
        ) VALUES(?, ?, ?, ?, ?, ?)
        """,
        (novel_id, 2, 3, "Volume Two Plan", "Goal for volume two", "Hook two"),
    )

    conn.execute(
        "INSERT INTO chapters(novel_id, chapter_no, content) VALUES(?, ?, ?)",
        (novel_id, 2, "前章内容" * 80),
    )
    chapter_id = conn.execute("SELECT id FROM chapters WHERE novel_id = ? AND chapter_no = 2", (novel_id,)).fetchone()[0]
    conn.execute(
        "INSERT INTO chapter_summaries(novel_id, chapter_id, short_summary) VALUES(?, ?, ?)",
        (novel_id, chapter_id, "上一章摘要"),
    )

    conn.commit()
    conn.close()


def test_get_chapter_plan_filters_by_volume_no(tmp_path):
    db_path = tmp_path / "task_card.db"
    _prepare_db(db_path)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    novel_id = conn.execute("SELECT id FROM novels WHERE slug = ?", ("demo_novel",)).fetchone()["id"]

    plan = get_chapter_plan(conn, novel_id, 3, volume_no=2)
    conn.close()

    assert plan is not None
    assert plan["planned_title"] == "Volume Two Plan"
    assert plan["chapter_goal"] == "Goal for volume two"


def test_build_task_card_uses_requested_volume_plan(tmp_path):
    db_path = tmp_path / "task_card.db"
    _prepare_db(db_path)

    markdown = build_task_card(
        3,
        {"db_path": str(db_path)},
        "demo_novel",
        volume_no=2,
    )

    assert "Volume Two Plan" in markdown
    assert "Goal for volume two" in markdown
    assert "Volume One Plan" not in markdown
