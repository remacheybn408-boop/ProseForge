#!/usr/bin/env python3
"""
Build a chapter task card from SQLite data.

Usage:
  python -m src.pipeline.task_card_builder 12 --novel-slug demo_novel
  python -m src.pipeline.task_card_builder 12 --volume-no 2 --output card.md
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from version import get_version
from src.utils.config_utils import DEFAULT_DB_PATH, load_json_config, resolve_path
from src.db._conn import connect_sqlite


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SLUG = "demo_novel"
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "task_cards"


def load_config(config_path: str | None) -> dict:
    """Load JSON config, falling back to defaults when absent."""
    return load_json_config(config_path, PROJECT_ROOT)


def get_db_path(config: dict) -> str:
    return str(resolve_path(PROJECT_ROOT, config.get("db_path", DEFAULT_DB_PATH)))


def get_novel_id(conn: sqlite3.Connection, slug: str) -> int | None:
    row = conn.execute("SELECT id FROM novels WHERE slug = ?", (slug,)).fetchone()
    return row["id"] if row else None


def get_prev_chapter_end(conn: sqlite3.Connection, novel_id: int, chapter_no: int) -> str:
    """Get the last roughly 200 Chinese characters of the previous chapter."""
    if chapter_no <= 1:
        return "(No previous chapter: this is an opening chapter.)"

    row = conn.execute(
        "SELECT content FROM chapters WHERE novel_id = ? AND chapter_no = ?",
        (novel_id, chapter_no - 1),
    ).fetchone()
    if not row or not row["content"]:
        return "(Previous chapter content not found.)"

    content = row["content"]
    tail = content[-400:] if len(content) > 400 else content
    chinese_chars = [char for char in tail if "\u4e00" <= char <= "\u9fff"]
    if len(chinese_chars) <= 200:
        return tail.strip()

    count = 0
    for index in range(len(tail) - 1, -1, -1):
        if "\u4e00" <= tail[index] <= "\u9fff":
            count += 1
            if count == 200:
                return tail[index:].strip()
    return tail.strip()


def get_chapter_plan(
    conn: sqlite3.Connection,
    novel_id: int,
    chapter_no: int,
    volume_no: int = 1,
) -> dict | None:
    """Read the chapter_plans row for a specific volume/chapter pair."""
    row = conn.execute(
        """
        SELECT chapter_goal, conflict_point, ending_hook_direction,
               continuity_from_previous, main_event, character_focus,
               must_include, plot_threads_to_advance, reader_promises_to_advance,
               planned_title
        FROM chapter_plans
        WHERE novel_id = ? AND volume_no = ? AND chapter_no = ?
        """,
        (novel_id, volume_no, chapter_no),
    ).fetchone()
    if not row:
        return None

    return {
        "chapter_goal": row["chapter_goal"] or "",
        "conflict_point": row["conflict_point"] or "",
        "ending_hook_direction": row["ending_hook_direction"] or "",
        "continuity_from_previous": row["continuity_from_previous"] or "",
        "main_event": row["main_event"] or "",
        "character_focus": row["character_focus"] or "",
        "must_include": row["must_include"] or "",
        "plot_threads_to_advance": row["plot_threads_to_advance"] or "",
        "reader_promises_to_advance": row["reader_promises_to_advance"] or "",
        "planned_title": row["planned_title"] or "",
    }


def get_prev_chapter_summary(conn: sqlite3.Connection, novel_id: int, chapter_no: int) -> str:
    if chapter_no <= 1:
        return "(No previous chapter summary.)"

    row = conn.execute(
        """
        SELECT cs.short_summary
        FROM chapter_summaries cs
        JOIN chapters c ON cs.chapter_id = c.id
        WHERE c.novel_id = ? AND c.chapter_no = ?
        """,
        (novel_id, chapter_no - 1),
    ).fetchone()
    return row["short_summary"] if row and row["short_summary"] else "(Previous chapter summary not found.)"


def get_anti_ai_rules(conn: sqlite3.Connection, novel_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT content FROM writing_rules
        WHERE novel_id = ? AND rule_type = 'anti_ai' AND status = 'active'
        """,
        (novel_id,),
    ).fetchall()
    return [row["content"] for row in rows if row["content"]]


def get_open_plot_threads(conn: sqlite3.Connection, novel_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT title FROM plot_threads WHERE novel_id = ? AND status = 'open'",
        (novel_id,),
    ).fetchall()
    return [row["title"] for row in rows if row["title"]]


def get_open_promises(conn: sqlite3.Connection, novel_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT promise_title FROM reader_promises WHERE novel_id = ? AND status = 'open'",
        (novel_id,),
    ).fetchall()
    return [row["promise_title"] for row in rows if row["promise_title"]]


def get_character_relations() -> list[dict]:
    """Read character relationships from the active workspace slot when available."""
    ws_dir = PROJECT_ROOT / "workspace"
    registry_path = ws_dir / "registry.json"
    if not registry_path.exists():
        return []

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    active_slot = registry.get("active_slot", "")
    if not active_slot:
        return []

    db_path = ws_dir / active_slot / "novel.db"
    if not db_path.exists():
        return []

    try:
        with closing(connect_sqlite(db_path)) as conn:
            rows = conn.execute(
                "SELECT char_a, char_b, relation_type FROM character_relationships"
            ).fetchall()
    except sqlite3.Error:
        return []
    return [{"char_a": row[0], "char_b": row[1], "type": row[2]} for row in rows]


def get_jury_feedback(chapter_no: int) -> dict | None:
    if chapter_no <= 1:
        return None

    jury_path = PROJECT_ROOT / "reports" / "agent_reviews" / f"chapter_{chapter_no - 1:03d}_agent_review.json"
    if not jury_path.exists():
        return None

    try:
        return json.loads(jury_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def build_task_card(
    chapter_no: int,
    config: dict,
    slug: str,
    volume_no: int = 1,
) -> str:
    """Build the full task card markdown."""
    db_path = Path(get_db_path(config))
    if not db_path.exists():
        return f"# Task Card - Chapter {chapter_no}\n\n> [WARN] Database not found: {db_path}\n"

    with closing(connect_sqlite(db_path)) as conn:
        conn.row_factory = sqlite3.Row
        novel_id = get_novel_id(conn, slug)
        if not novel_id:
            return f"# Task Card - Chapter {chapter_no}\n\n> [WARN] Novel `{slug}` is not registered in the database.\n"

        plan = get_chapter_plan(conn, novel_id, chapter_no, volume_no=volume_no)
        prev_end = get_prev_chapter_end(conn, novel_id, chapter_no)
        prev_summary = get_prev_chapter_summary(conn, novel_id, chapter_no)
        anti_rules = get_anti_ai_rules(conn, novel_id)
        plot_threads = get_open_plot_threads(conn, novel_id)
        promises = get_open_promises(conn, novel_id)

    jury = get_jury_feedback(chapter_no)
    relations = get_character_relations()
    title_line = plan["planned_title"] if plan and plan.get("planned_title") else f"Chapter {chapter_no}"

    lines: list[str] = [
        f"# Task Card - {title_line}",
        "",
        f"> Novel: {slug} | Volume: {volume_no} | Chapter: {chapter_no}",
        "",
        "## 1. Previous Chapter Ending",
        "",
        "```text",
        prev_end,
        "```",
        "",
    ]

    if prev_summary and "not found" not in prev_summary.lower():
        lines.extend([f"Previous summary: {prev_summary}", ""])

    lines.extend(["## 2. Chapter Plan", ""])
    if plan:
        for label, key in [
            ("Goal", "chapter_goal"),
            ("Conflict", "conflict_point"),
            ("Ending hook", "ending_hook_direction"),
            ("Main event", "main_event"),
            ("Character focus", "character_focus"),
            ("Must include", "must_include"),
        ]:
            if plan.get(key):
                lines.append(f"- {label}: {plan[key]}")
    else:
        lines.append("> [WARN] No chapter plan found for this volume/chapter pair.")
    lines.append("")

    if relations:
        relation_lines = []
        for relation in relations:
            relation_lines.append(f"- {relation['char_a']} - {relation['type']} - {relation['char_b']}")
        if relation_lines:
            lines.extend(["## 3. Character Relationships", "", *relation_lines[:20], ""])

    lines.extend(["## 4. Continuity Requirements", ""])
    if plan and plan.get("continuity_from_previous"):
        lines.append(f"- Required carry-over: {plan['continuity_from_previous']}")
    if plot_threads:
        lines.append("- Open plot threads:")
        lines.extend([f"  - {item}" for item in plot_threads[:10]])
    if promises:
        lines.append("- Open reader promises:")
        lines.extend([f"  - {item}" for item in promises[:10]])
    if plan and plan.get("plot_threads_to_advance"):
        lines.append(f"- Advance these threads: {plan['plot_threads_to_advance']}")
    if plan and plan.get("reader_promises_to_advance"):
        lines.append(f"- Advance these promises: {plan['reader_promises_to_advance']}")
    lines.append("")

    lines.extend(["## 5. Writing Constraints", ""])
    if anti_rules:
        lines.extend([f"- {rule}" for rule in anti_rules])
    else:
        lines.extend(
            [
                "- Avoid abstract summary paragraphs that explain everything.",
                "- Prefer concrete actions, objects, and dialogue over exposition.",
                "- Avoid templated transitions and generic AI-sounding conclusions.",
                "- Each major action should create a visible consequence.",
            ]
        )
    lines.append("")

    if jury and jury.get("chief_editor"):
        chief_editor = jury.get("chief_editor", {})
        lines.extend([f"## 6. Previous Review (Chapter {chapter_no - 1})", ""])
        lines.append(f"> Overall score: {jury.get('overall_score', '?')} | Status: {jury.get('status', '?')}")
        lines.append("")
        for section_title, key in [("Must fix", "must_fix"), ("Should fix", "should_fix")]:
            items = chief_editor.get(key, [])
            if items:
                lines.append(f"### {section_title}")
                for index, item in enumerate(items, 1):
                    message = item.get("message", str(item))
                    suggestion = item.get("suggestion", "")
                    lines.append(f"{index}. {message}")
                    if suggestion:
                        lines.append(f"   Suggestion: {suggestion}")
                lines.append("")

    lines.extend(
        [
            "## 7. Post Checks",
            "",
            "- Word count is within the expected range.",
            "- The opening continues naturally from the previous chapter.",
            "- New facts are grounded in existing canon.",
            "- The chapter ends with clear reader pull.",
            "",
            "---",
            f"*Generated by task_card_builder {get_version()}*",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a chapter task card from SQLite data.")
    parser.add_argument("chapter_no", type=int, help="Chapter number to build.")
    parser.add_argument("--config", default=None, help="Optional JSON config path.")
    parser.add_argument("--novel-slug", default=DEFAULT_SLUG, help="Novel slug.")
    parser.add_argument("--volume-no", type=int, default=1, help="Volume number for chapter plan lookup.")
    parser.add_argument("--output", default=None, help="Optional markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    markdown = build_task_card(
        args.chapter_no,
        config,
        args.novel_slug,
        volume_no=args.volume_no,
    )
    output_path = Path(args.output) if args.output else DEFAULT_OUTPUT_DIR / f"chapter_{args.chapter_no:03d}_task_card.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
