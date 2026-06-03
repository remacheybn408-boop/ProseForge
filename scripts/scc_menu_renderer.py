#!/usr/bin/env python3
"""scc_menu_renderer.py — 从 configs/scc_menu.json 生成统一菜单输出."""
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_menu():
    return json.loads((PROJECT_ROOT / "configs" / "scc_menu.json").read_text(encoding="utf-8"))


def render_hermes_menu():
    """生成 Hermes 聊天用菜单文本."""
    menu = load_menu()
    lines = ["【SCC 小说写作菜单】\n"]
    for i, section in enumerate(menu["sections"], 1):
        lines.append(f"{i}. {section['title']}")
        lines.append(f"   {section['description']}\n")
    lines.append("回复数字，或直接说你的目标。")
    return "\n".join(lines)


def render_cli_menu():
    """生成 CLI 文本菜单."""
    menu = load_menu()
    lines = ["=" * 60, f"  SCC 菜单 v{menu['version']}", "=" * 60, ""]
    for i, section in enumerate(menu["sections"], 1):
        lines.append(f"  [{i}] {section['title']}")
        for item in section["items"]:
            danger = "⚠" if item["danger"] == "dangerous" else " "
            lines.append(f"      {danger} {item['label']}")
    return "\n".join(lines)


def render_markdown_user_guide():
    """生成 docs/SCC_USER_MENU.md."""
    menu = load_menu()
    lines = [
        "# SCC 小说写作菜单",
        "",
        "> 在 Hermes 里输入「菜单」，或在终端运行 `python novel.py scc-help`。",
        "",
        "---",
        "",
    ]
    for section in menu["sections"]:
        lines.append(f"## {section['title']}")
        lines.append("")
        lines.append(section["description"])
        lines.append("")
        for item in section["items"]:
            prefix = "> ⚠️ **危险操作** — " if item.get("danger") == "dangerous" else ""
            lines.append(f"- **{item['label']}** — {item.get('description', item.get('answer', ''))}")
            if item.get("danger") == "dangerous":
                lines.append(f"  {prefix}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--hermes":
        print(render_hermes_menu())
    elif len(sys.argv) > 1 and sys.argv[1] == "--markdown":
        (PROJECT_ROOT / "docs" / "SCC_USER_MENU.md").write_text(
            render_markdown_user_guide(), encoding="utf-8")
        print("docs/SCC_USER_MENU.md generated")
    else:
        print(render_cli_menu())
