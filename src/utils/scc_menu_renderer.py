#!/usr/bin/env python3
"""scc_menu_renderer.py — Universal menu rendering library.

Single source of truth: configs/scc_menu.json.
All menu rendering paths (MCP, CLI, Hermes) delegate here.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ── Data loading ───────────────────────────────────────────────

def load_menu() -> dict:
    """Load scc_menu.json as dict."""
    return json.loads((PROJECT_ROOT / "configs" / "scc_menu.json").read_text(encoding="utf-8"))


def load_project_status() -> dict:
    """Load current project status — consolidated from hermes + MCP status loaders."""
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"

    status = {
        "version": "v0.7.1",
        "ok": False,
        "initialized": False,
        "has_workspace": False,
        "active_slot": "",
        "novel_title": "",
        "has_outline": False,
        "outline_title": "",
        "chapter_count": 0,
        "total_words": 0,
        "slot_count": 0,
        "db_ok": False,
    }

    if not reg_file.exists():
        return status

    try:
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        status["has_workspace"] = True
        status["initialized"] = True
        status["active_slot"] = reg.get("active_slot", "")
        status["slot_count"] = len(reg.get("slots", []))

        active = status["active_slot"]
        if not active:
            return status

        slot_dir = ws / active
        db_path = slot_dir / "novel.db"
        proj_file = slot_dir / "project.json"

        if db_path.exists():
            import sqlite3
            try:
                conn = sqlite3.connect(str(db_path))
                conn.row_factory = sqlite3.Row
                row = conn.execute("SELECT title FROM novels LIMIT 1").fetchone()
                if row:
                    status["novel_title"] = row["title"]
                ch_row = conn.execute(
                    "SELECT COUNT(*) as cnt, COALESCE(SUM(word_count),0) as wc FROM chapters"
                ).fetchone()
                if ch_row:
                    status["chapter_count"] = ch_row["cnt"] or 0
                    status["total_words"] = ch_row["wc"] or 0
                status["db_ok"] = True
                conn.close()
            except Exception:
                pass

        if proj_file.exists():
            try:
                proj = json.loads(proj_file.read_text(encoding="utf-8"))
                oid = proj.get("active_outline", "")
                if oid:
                    status["has_outline"] = True
                    outlines_dir = slot_dir / "outlines"
                    o_file = outlines_dir / f"{oid}.json"
                    if o_file.exists():
                        o_data = json.loads(o_file.read_text(encoding="utf-8"))
                        status["outline_title"] = o_data.get("title", "")
                        if not status["chapter_count"]:
                            status["chapter_count"] = o_data.get("chapter_count", 0)
            except Exception:
                pass

        status["ok"] = True
    except Exception:
        pass

    return status


# ── Section helpers ────────────────────────────────────────────

def get_section(section_id: str) -> dict | None:
    """Get a menu section by id."""
    menu = load_menu()
    for s in menu["sections"]:
        if s["id"] == section_id:
            return s
    return None


def get_sections(exclude_faq: bool = True) -> list[dict]:
    """Get all menu sections, optionally excluding FAQ."""
    menu = load_menu()
    if exclude_faq:
        return [s for s in menu["sections"] if s["id"] != "faq"]
    return list(menu["sections"])


# ── Rendering: main menu ───────────────────────────────────────

def render_status_summary(status: dict) -> str:
    """Render a compact status summary line."""
    lines = []
    lines.append("=" * 58)
    lines.append(f"  小说引擎 {status.get('version', 'v0.7.1')} — 中文菜单")
    lines.append("=" * 58)
    lines.append("")

    if status.get("ok", False) and status.get("novel_title"):
        lines.append(f"  📖 当前小说：{status['novel_title']}")
        lines.append(f"  📂 当前档案：{status.get('active_slot', '')}")
        if status.get("has_outline", False):
            lines.append(f"  📝 大纲状态：已激活 ({status.get('outline_title', '')})")
        else:
            lines.append(f"  📝 大纲状态：未添加")
        lines.append(f"  📄 章节数量：{status.get('chapter_count', 0)} 章")
        if status.get("total_words", 0) > 0:
            lines.append(f"  🔤 总字数：{status['total_words']:,} 字")
        if status.get("chapter_count", 0) > 0:
            lines.append(f"  ✅ 当前状态：可以继续写作或审稿")
        elif status.get("has_outline", False):
            lines.append(f"  ✅ 当前状态：有大纲，可以开始写第一章")
        else:
            lines.append(f"  ⚠️  当前状态：还不能开写，请先添加大纲")
    elif status.get("has_workspace", False):
        lines.append(f"  📂 项目已初始化，还没有小说")
        lines.append(f"  💡 推荐：先添加大纲，自动创建小说项目")
    else:
        lines.append(f"  ⚠️  项目尚未初始化")
        lines.append(f"  💡 推荐：先运行 nf_初化 工具")
    return "\n".join(lines)


def render_main_menu(status: dict = None, style: str = "mcp") -> str:
    """Unified main menu for MCP / CLI / Hermes.

    style is reserved for future customization; currently outputs same format.
    """
    if status is None:
        status = load_project_status()

    lines = []
    lines.append(render_status_summary(status))

    sections = get_sections(exclude_faq=True)
    lines.append("")
    lines.append("  ─" * 18)
    lines.append("  主菜单")
    lines.append("  ─" * 18)
    for i, sec in enumerate(sections, 1):
        # Strip emoji for cleaner display
        title = sec["title"]
        lines.append(f"  [{i}] {title}")
    lines.append("")
    lines.append("  💬 你可以直接说：")
    lines.append("   「添加大纲」「写第一章」「审稿」「导出 TXT」")
    lines.append("   「查看状态」「有哪些小说」「角色精神状态」")
    lines.append("")

    return "\n".join(lines)


# ── Rendering: sub-menus ───────────────────────────────────────

def render_sub_menu(menu_type: str, status: dict = None) -> str:
    """Render a sub-menu text for a given menu type (hermes-style)."""
    if status is None:
        status = load_project_status()

    # Known sub-menu types → section id mapping
    section_map = {
        "outline": "outline",
        "db": "archive",
        "writing": "writing",
        "novice": "start",
        "character": "character",
        "quality": "quality",
        "story": "quality",
        "memory": "memory",
    }

    section_id = section_map.get(menu_type, menu_type)
    section = get_section(section_id)
    if not section:
        return f"【未知菜单】: {menu_type}"

    lines = [f"【{section['title']}】"]
    if status.get("novel_title"):
        lines.append(f"当前：{status['novel_title']} ({status.get('active_slot', '')})")
    lines.append("")

    for i, item in enumerate(section["items"], 1):
        prefix = "⚠ " if item.get("danger") == "dangerous" else "  "
        lines.append(f"  [{i}] {prefix}{item['label']}")
    lines.append("")
    lines.append("  [0] 返回主菜单")
    return "\n".join(lines)


# ── Rendering: user guide ──────────────────────────────────────

def render_user_guide() -> str:
    """Generate full user guide / help text from scc_menu.json.

    Replaces the old 180-line hardcoded cmd_scc_help().
    """
    menu = load_menu()
    v = menu.get("version", "v0.7.1")
    lines = [
        "=" * 68,
        f"  小说写作流水线 — 操作手册",
        f"  Novel Forge {v}",
        "=" * 68,
        "",
        "  nf_xxx 工具是所有操作的统一入口。",
        "",
        "  ── Hermes/Agent 用户 ──",
        "  如果你是 Hermes Agent 用户，可以直接用自然语言与我对话：",
        "  · 说「我要写第3章」→ 我会检查上下文并生成任务卡",
        "  · 说「添加大纲」→ 我会引导你上传或粘贴大纲内容",
        "  · 说「审稿第1章」→ 我会运行 Agent 陪审团审查",
        "  · 说「导出小说」→ 我会帮你导出 Markdown",
        "  · 说「菜单」→ 我会显示交互式中文菜单",
        "",
        "  ── CLI/终端用户 ──",
        "  以下按功能分类列出常用命令。",
        "",
    ]

    for section in menu["sections"]:
        sid = section["id"]
        lines.append("  " + "─" * 60)

        if sid == "faq":
            # FAQ section — render Q&A format
            lines.append("  【常见问题 FAQ】")
            lines.append("  " + "━" * 60)
            lines.append("")
            for item in section["items"]:
                q = item.get("label", "")
                a = item.get("answer", "")
                if q:
                    lines.append(f"  Q: {q}")
                if a:
                    for para in a.split("\n"):
                        lines.append(f"  A: {para}")
                lines.append("")
            continue

        # Normal section
        lines.append(f"  【{section['title']}】")
        lines.append("")

        for item in section["items"]:
            usage = item.get("usage", item.get("command", ""))
            desc = item.get("description", "")
            if usage:
                # Pad usage to ~35 chars for alignment
                lines.append(f"  {usage:<45s}{desc}")
            elif desc:
                lines.append(f"  {desc}")

        lines.append("")

    lines.append("  " + "━" * 60)
    lines.append("  使用 Hermes nf_xxx 工具进行操作")
    lines.append("  " + "━" * 60)
    lines.append("")

    return "\n".join(lines)


# ── Rendering: interactive section ─────────────────────────────

def render_section_items(section_id: str) -> list[dict]:
    """Get render-ready items for a section (for CLI interactive menus)."""
    section = get_section(section_id)
    if not section:
        return []
    return section.get("items", [])


# ── CLI entry point ────────────────────────────────────────────

