#!/usr/bin/env python3
"""
task_card_builder.py — Build chapter task card from SQLite data v0.5.0

Reads a chapter plan + previous chapter data from SQLite and produces a
structured Markdown task card at:

  outputs/task_cards/chapter_NNN_task_card.md

Usage:
  python -m src.task_card.task_card_builder <chapter_no> [--config config.json] [--novel-slug demo_novel]
"""

import json
import sqlite3
import sys
import argparse
import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SLUG = "demo_novel"
DEFAULT_CONFIG = PROJECT_ROOT / "config.json"


def load_config(config_path: str | None) -> dict:
    """Load JSON config, falling back to defaults."""
    cfg = {}
    if config_path:
        p = Path(config_path)
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                cfg = json.load(f)
    return cfg


def get_db_path(config: dict) -> str:
    return config.get("db_path", str(PROJECT_ROOT / "data" / "novel_memory.db"))


def get_novel_id(conn: sqlite3.Connection, slug: str) -> int | None:
    try:
        cur = conn.execute("SELECT id FROM novels WHERE slug = ?", (slug,))
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def get_prev_chapter_end(conn: sqlite3.Connection, novel_id: int, chapter_no: int) -> str:
    """Get last ~200 chars of previous chapter's content."""
    if chapter_no <= 1:
        return "(无上一章 — 本章为开头章节)"
    try:
        cur = conn.execute(
            "SELECT content FROM chapters WHERE novel_id = ? AND chapter_no = ?",
            (novel_id, chapter_no - 1),
        )
        row = cur.fetchone()
        if row and row[0]:
            content = row[0]
            tail = content[-400:] if len(content) > 400 else content
            # Take last ~200 Chinese chars
            chinese_chars = [c for c in tail if '\u4e00' <= c <= '\u9fff']
            if len(chinese_chars) > 200:
                # Find position of the 200th-from-last Chinese char
                count = 0
                for i in range(len(tail) - 1, -1, -1):
                    if '\u4e00' <= tail[i] <= '\u9fff':
                        count += 1
                        if count == 200:
                            return tail[i:].strip()
                return tail.strip()
            return tail.strip()
        return "(上一章内容为空)"
    except Exception as e:
        return f"(读取上一章失败: {e})"


def get_chapter_plan(conn: sqlite3.Connection, novel_id: int, chapter_no: int) -> dict | None:
    """Read chapter_plans row for this chapter."""
    try:
        cur = conn.execute(
            """SELECT chapter_goal, conflict_point, ending_hook_direction,
                      continuity_from_previous, main_event, character_focus,
                      must_include, plot_threads_to_advance, reader_promises_to_advance,
                      planned_title
               FROM chapter_plans
               WHERE novel_id = ? AND chapter_no = ?""",
            (novel_id, chapter_no),
        )
        row = cur.fetchone()
        if row:
            return {
                "chapter_goal": row[0] or "",
                "conflict_point": row[1] or "",
                "ending_hook_direction": row[2] or "",
                "continuity_from_previous": row[3] or "",
                "main_event": row[4] or "",
                "character_focus": row[5] or "",
                "must_include": row[6] or "",
                "plot_threads_to_advance": row[7] or "",
                "reader_promises_to_advance": row[8] or "",
                "planned_title": row[9] or "",
            }
        return None
    except Exception:
        return None


def get_prev_chapter_summary(conn: sqlite3.Connection, novel_id: int, chapter_no: int) -> str:
    """Get short summary of previous chapter."""
    if chapter_no <= 1:
        return "(无上一章)"
    try:
        cur = conn.execute(
            """SELECT cs.short_summary
               FROM chapter_summaries cs
               JOIN chapters c ON cs.chapter_id = c.id
               WHERE c.novel_id = ? AND c.chapter_no = ?""",
            (novel_id, chapter_no - 1),
        )
        row = cur.fetchone()
        if row and row[0]:
            return row[0]
        return "(无摘要)"
    except Exception:
        return "(查询失败)"


def get_anti_ai_rules(conn: sqlite3.Connection, novel_id: int) -> list[str]:
    """Get anti-AI rules from writing_rules."""
    try:
        cur = conn.execute(
            """SELECT content FROM writing_rules
               WHERE novel_id = ? AND rule_type = 'anti_ai' AND status = 'active'""",
            (novel_id,),
        )
        return [row[0] for row in cur.fetchall() if row[0]]
    except Exception:
        return []


def get_open_plot_threads(conn: sqlite3.Connection, novel_id: int) -> list[str]:
    """Get unresolved plot threads."""
    try:
        cur = conn.execute(
            "SELECT title FROM plot_threads WHERE novel_id = ? AND status = 'open'",
            (novel_id,),
        )
        return [row[0] for row in cur.fetchall()]
    except Exception:
        return []


def get_open_promises(conn: sqlite3.Connection, novel_id: int) -> list[str]:
    """Get unfulfilled reader promises."""
    try:
        cur = conn.execute(
            "SELECT promise_title FROM reader_promises WHERE novel_id = ? AND status = 'open'",
            (novel_id,),
        )
        return [row[0] for row in cur.fetchall()]
    except Exception:
        return []


def build_task_card(chapter_no: int, config: dict, slug: str) -> str:
    """Build full task card markdown."""
    db_path = get_db_path(config)
    if not Path(db_path).exists():
        return f"# 任务卡 — 第{chapter_no}章\n\n> [WARN] 数据库不存在: {db_path}\n\n请先初始化数据库。"

    conn = sqlite3.connect(db_path)
    novel_id = get_novel_id(conn, slug)
    if not novel_id:
        conn.close()
        return f"# 任务卡 — 第{chapter_no}章\n\n> [WARN] 小说 `{slug}` 未在数据库中注册。"

    plan = get_chapter_plan(conn, novel_id, chapter_no)
    prev_end = get_prev_chapter_end(conn, novel_id, chapter_no)
    prev_summary = get_prev_chapter_summary(conn, novel_id, chapter_no)

    title_line = plan["planned_title"] if plan and plan.get("planned_title") else f"第{chapter_no}章"

    lines = []
    lines.append(f"# 任务卡 — {title_line}")
    lines.append(f"")
    lines.append(f"> 章节编号: {chapter_no} | 小说: {slug} | 生成时间: 自动")
    lines.append(f"")

    # ═══════════ 1. 上章结尾 ═══════════
    lines.append("## 1. 上章结尾")
    lines.append("")
    lines.append("以下是上一章最后的内容，本章开头必须自然承接：")
    lines.append("")
    lines.append("```")
    lines.append(prev_end)
    lines.append("```")
    lines.append("")

    if prev_summary and prev_summary != "(无摘要)" and prev_summary != "(无上一章)" and prev_summary != "(查询失败)":
        lines.append(f"**上章摘要:** {prev_summary}")
        lines.append("")

    # ═══════════ 2. 本章骨架 ═══════════
    lines.append("## 2. 本章骨架 (来自大纲)")
    lines.append("")
    if plan:
        if plan.get("chapter_goal"):
            lines.append(f"- **本章目标:** {plan['chapter_goal']}")
        if plan.get("conflict_point"):
            lines.append(f"- **冲突点:** {plan['conflict_point']}")
        if plan.get("ending_hook_direction"):
            lines.append(f"- **结尾钩子方向:** {plan['ending_hook_direction']}")
        if plan.get("main_event"):
            lines.append(f"- **主要事件:** {plan['main_event']}")
        if plan.get("character_focus"):
            lines.append(f"- **角色聚焦:** {plan['character_focus']}")
        if plan.get("must_include"):
            lines.append(f"- **必须包含:** {plan['must_include']}")
    else:
        lines.append("> [WARN] 未找到本章大纲数据 (chapter_plans 表可能为空)")
    lines.append("")

    # ═══════════ 3. 必须承接 ═══════════
    lines.append("## 3. 必须承接 (连续性要求)")
    lines.append("")
    if plan and plan.get("continuity_from_previous"):
        lines.append(f"大纲要求承接: {plan['continuity_from_previous']}")
        lines.append("")

    # Open plot threads
    plot_threads = get_open_plot_threads(conn, novel_id)
    if plot_threads:
        lines.append("**未闭合的伏笔线索:**")
        for pt in plot_threads[:10]:
            lines.append(f"- {pt}")
        lines.append("")

    # Open promises
    promises = get_open_promises(conn, novel_id)
    if promises:
        lines.append("**未兑现的读者承诺:**")
        for p in promises[:10]:
            lines.append(f"- {p}")
        lines.append("")

    if plan and plan.get("plot_threads_to_advance"):
        lines.append(f"**本章应推进的伏笔:** {plan['plot_threads_to_advance']}")
        lines.append("")

    if plan and plan.get("reader_promises_to_advance"):
        lines.append(f"**本章应推进的承诺:** {plan['reader_promises_to_advance']}")
        lines.append("")

    # ═══════════ 4. 本章禁止 ═══════════
    lines.append("## 4. 本章禁止 (禁忌写法)")
    lines.append("")

    anti_rules = get_anti_ai_rules(conn, novel_id)
    if anti_rules:
        for rule in anti_rules:
            lines.append(f"- {rule}")
    else:
        lines.append("- 禁止 AI 总结腔：不要在段落结尾做 \"这一切说明…\"、\"由此可见…\"")
        lines.append("- 禁止模板化转场：避免 \"与此同时…\"、\"另一方面…\" 反复使用")
        lines.append("- 禁止抽象说明：用具体动作/对话/场景替代概念说明")
        lines.append("- 禁止说明书腔：不要在叙述中突然开始解释设定")
        lines.append("- 禁止无后果行动：每个行动都要有可见的、具体的后果")
    lines.append("")

    # ═══════════ 5. 追读钩子 ═══════════
    lines.append("## 5. 追读钩子")
    lines.append("")
    lines.append("- **开头钩子:** 第一段必须引发好奇或紧张，不许从 \"清晨，阳光…\" 开始")
    lines.append("- **中间压力:** 第2-3个场景必须出现压力升级或意外转折")
    if plan and plan.get("ending_hook_direction"):
        lines.append(f"- **结尾钩子:** {plan['ending_hook_direction']}")
    else:
        lines.append("- **结尾钩子:** 章末必须留悬念、提问或未完成动作，不可用 \"他继续修炼\" 结尾")
    lines.append("")

    # ═══════════ 6. 审稿重点 ═══════════
    lines.append("## 6. 审稿重点 (post 阶段检查)")
    lines.append("")
    lines.append("- 字数是否在合理范围？")
    lines.append("- 是否承接了上章结尾的状态/钩子？")
    lines.append("- 是否出现了无依据的新设定（幻觉）？")
    lines.append("- 是否存在 AI 腔 / 模板腔 / 说明书腔？")
    lines.append("- 角色口吻是否符合声纹设定？")
    lines.append("- 行动是否有可见后果（scene_causality）？")
    lines.append("- 对白是否自然？是否有对白节拍变化？")
    lines.append("- 是否有 \"追读钩子\" 让读者想翻下一章？")
    lines.append("")
    lines.append("---")
    lines.append(f"*由 task_card_builder {get_version()} 自动生成*")
    lines.append("")

    conn.close()
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Build chapter task card from SQLite data",
    )
    parser.add_argument("chapter_no", type=int, help="Chapter number")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.json")
    parser.add_argument("--novel-slug", default=DEFAULT_SLUG, help="Novel slug")
    args = parser.parse_args()

    config = load_config(args.config)
    slug = args.novel_slug

    print(f"Building task card for chapter {args.chapter_no} (slug: {slug})...")

    markdown = build_task_card(args.chapter_no, config, slug)

    # Ensure output directory
    output_dir = PROJECT_ROOT / "outputs" / "task_cards"
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"chapter_{args.chapter_no:03d}_task_card.md"
    output_path = output_dir / filename
    output_path.write_text(markdown, encoding="utf-8")

    print(f"Task card written to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
