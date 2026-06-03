#!/usr/bin/env python3
"""
task_card_builder.py — 章节任务卡构建入口脚本 v0.5.0

Thin wrapper around src/task_card/task_card_builder.py.
Provides a command-line interface for generating chapter task cards.

Usage:
  python scripts/task_card_builder.py <chapter_no> [--config config.json] [--novel-slug demo_novel]

Output:
  outputs/task_cards/chapter_NNN_task_card.md
"""

import sys
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Ensure src is importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Main entry point — delegates to src.task_card.task_card_builder."""
    try:
        from src.task_card.task_card_builder import main as builder_main
        return builder_main()
    except ImportError as e:
        print(f"[ERROR] Cannot import src.task_card.task_card_builder: {e}")
        print("[INFO] Ensure the src package is properly structured:")
        print(f"       src/task_card/task_card_builder.py must exist.")
        print("[INFO] Falling back to standalone implementation.")

        # Standalone fallback
        return _standalone_main()
    except Exception as e:
        print(f"[ERROR] Task card builder failed: {e}")
        return 1


def _standalone_main():
    """Standalone fallback implementation."""
    import argparse
    import json
    import sqlite3

    parser = argparse.ArgumentParser(
        description="Build chapter task card from SQLite data",
    )
    parser.add_argument(
        "chapter_no", type=int, help="Chapter number",
    )
    parser.add_argument(
        "--config", default=str(PROJECT_ROOT / "config.json"),
        help="Path to config.json",
    )
    parser.add_argument(
        "--novel-slug", default="demo_novel",
        help="Novel slug identifier",
    )
    args = parser.parse_args()

    # Load config
    config = {}
    config_path = Path(args.config)
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[WARN] Cannot parse config: {e}")

    db_path = config.get("db_path", str(PROJECT_ROOT / "data" / "novel_memory.db"))
    db_full = Path(db_path)
    if not db_full.is_absolute():
        db_full = PROJECT_ROOT / db_path

    if not db_full.exists():
        print(f"[ERROR] Database not found: {db_full}")
        print("[INFO] Run scripts/init_db.py first.")
        return 1

    try:
        conn = sqlite3.connect(str(db_full))
    except Exception as e:
        print(f"[ERROR] Cannot connect to database: {e}")
        return 1

    slug = args.novel_slug
    chapter_no = args.chapter_no

    # Get novel_id
    cur = conn.execute("SELECT id, title FROM novels WHERE slug = ?", (slug,))
    row = cur.fetchone()
    if not row:
        print(f"[ERROR] Novel '{slug}' not found in database.")
        conn.close()
        return 1

    novel_id, novel_title = row

    # Get chapter plan
    cur = conn.execute(
        """SELECT chapter_goal, conflict_point, ending_hook_direction,
                  continuity_from_previous, main_event, character_focus,
                  must_include, plot_threads_to_advance,
                  reader_promises_to_advance, planned_title
           FROM chapter_plans
           WHERE novel_id = ? AND chapter_no = ?""",
        (novel_id, chapter_no),
    )
    plan_row = cur.fetchone()

    # Get previous chapter tail
    prev_tail = "(无上一章 — 本章为开头章节)"
    if chapter_no > 1:
        cur = conn.execute(
            "SELECT content FROM chapters WHERE novel_id = ? AND chapter_no = ?",
            (novel_id, chapter_no - 1),
        )
        prev_row = cur.fetchone()
        if prev_row and prev_row[0]:
            content = prev_row[0]
            tail = content[-400:] if len(content) > 400 else content
            prev_tail = tail.strip()

    # Build markdown
    lines = []
    title = plan_row[9] if plan_row and plan_row[9] else f"第{chapter_no}章"
    lines.append(f"# 任务卡 — {title}")
    lines.append(f"")
    lines.append(f"> 章节编号: {chapter_no} | 小说: {slug}")
    lines.append(f"")

    lines.append("## 1. 上章结尾")
    lines.append("")
    lines.append("```")
    lines.append(prev_tail)
    lines.append("```")
    lines.append("")

    lines.append("## 2. 本章骨架")
    lines.append("")
    if plan_row:
        fields = [
            ("本章目标", 0), ("冲突点", 1), ("结尾钩子方向", 2),
            ("连续性承接", 3), ("主要事件", 4), ("角色聚焦", 5),
            ("必须包含", 6),
        ]
        for label, idx in fields:
            if plan_row[idx]:
                lines.append(f"- **{label}:** {plan_row[idx]}")
    else:
        lines.append("> [WARN] 未找到本章大纲数据。")
    lines.append("")

    lines.append("## 3. 本章禁止")
    lines.append("")
    lines.append("- 禁止 AI 总结腔")
    lines.append("- 禁止模板化转场")
    lines.append("- 禁止抽象说明")
    lines.append("- 禁止无后果行动")
    lines.append("")

    lines.append("## 4. 审稿重点")
    lines.append("")
    lines.append("- 字数合理范围")
    lines.append("- 连续性承接")
    lines.append("- 设定一致性")
    lines.append("- AI腔 / 水文检测")
    lines.append("- 角色口吻")
    lines.append("- 追读钩子")
    lines.append("")

    lines.append("---")
    lines.append(f"*由 task_card_builder {get_version()} 生成*")
    lines.append("")

    markdown = "\n".join(lines)
    conn.close()

    # Write output
    output_dir = PROJECT_ROOT / "outputs" / "task_cards"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"chapter_{chapter_no:03d}_task_card.md"
    output_path.write_text(markdown, encoding="utf-8")

    print(f"Task card written to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
