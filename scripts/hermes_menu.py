#!/usr/bin/env python3
"""hermes_menu.py — 普通用户菜单生成器 v0.6.5-clean8

提供给 Hermes Agent 调用，输出纯文本菜单，不暴露终端命令。
所有输出都是自然语言，适合直接展示给普通用户。
"""

import json
import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def get_project_status() -> dict:
    """获取当前项目状态（供 Hermes 格式化菜单用）"""
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"

    status = {
        "version": "v0.6.5",
        "ok": False,
        "has_workspace": False,
        "active_slot": "",
        "novel_title": "",
        "has_outline": False,
        "outline_title": "",
        "chapter_count": 0,
        "total_words": 0,
        "slot_count": 0,
    }

    if not reg_file.exists():
        return status

    try:
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        status["has_workspace"] = True
        status["active_slot"] = reg.get("active_slot", "")
        status["slot_count"] = len(reg.get("slots", []))

        active = status["active_slot"]
        if not active:
            return status

        slot_dir = ws / active
        db_path = slot_dir / "novel.db"
        proj_file = slot_dir / "project.json"

        if db_path.exists():
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
            conn.close()

        if proj_file.exists():
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

        status["ok"] = True
    except Exception:
        pass

    return status


def render_main_menu(status: dict) -> str:
    """生成普通用户主菜单文本"""
    lines = []
    lines.append("═══════════════════════════════════")
    lines.append(f"  小说写作引擎 v0.6.5")
    lines.append("═══════════════════════════════════")
    lines.append("")

    if status["ok"] and status["novel_title"]:
        lines.append(f"  当前小说：{status['novel_title']}")
        lines.append(f"  当前档案：{status['active_slot']}")
        if status["has_outline"]:
            lines.append(f"  大纲状态：已激活（{status['outline_title']}）")
            lines.append(f"  章节数量：{status['chapter_count']} 章 / {status['total_words']:,} 字")
            if status["chapter_count"] > 0:
                lines.append(f"  当前状态：可以继续写作")
            else:
                lines.append(f"  当前状态：有大纲，可以开始写第一章")
        else:
            lines.append(f"  大纲状态：未添加")
            lines.append(f"  当前状态：还不能开写，请先添加大纲")
    elif status["has_workspace"]:
        lines.append(f"  当前状态：已初始化，还没有小说项目")
    else:
        lines.append(f"  当前状态：首次使用，需要初始化")

    lines.append("")
    lines.append("  请选择你要做的事：")
    lines.append("  ────────────────────────────────")
    lines.append("  [1] 新手检查      环境诊断 & 项目初始化")
    lines.append("  [2] 小说档案库    管理多本小说独立存档")
    lines.append("  [3] 大纲管理      添加/切换/对比大纲")
    lines.append("  [4] 开始写作      pre → 写作 → post → review")
    lines.append("  [5] Agent 陪审团   18 Agent 审稿")
    lines.append("  [6] Story Contract  章节合同与提交")
    lines.append("  [7] 报告与导出    守卫报告 & 导出小说")
    lines.append("  [8] 操作手册      第一次怎么用")
    lines.append("  [9] 高级功能      终端命令 & 开发者工具")
    lines.append("  [0] 退出")
    lines.append("")
    lines.append("  推荐下一步：")
    if not status["has_workspace"]:
        lines.append("  → 新用户：回复 1，做新手检查（初始化项目）")
    elif not status["has_outline"]:
        lines.append("  → 还没有大纲：回复 3，添加大纲")
    elif status["chapter_count"] == 0:
        lines.append("  → 有大纲还没写：回复 4，开始写第一章")
    else:
        lines.append("  → 继续写：回复 4，进入写作流程")
        lines.append("  → 审稿：回复 5，AI 帮你检查质量")
    lines.append("")
    lines.append("  你也可以直接说：")
    lines.append("  「添加大纲」「写第一章」「导出小说」「审稿」")
    lines.append("")

    return "\n".join(lines)


def render_sub_menu(menu_type: str, status: dict) -> str:
    """生成子菜单"""
    menus = {
        "outline": [
            "【大纲管理】",
            f"当前大纲：{status.get('outline_title') or '无'}",
            "",
            "[1] 添加新大纲",
            "[2] 查看所有大纲",
            "[3] 切换大纲",
            "[4] 对比大纲",
            "[5] 回滚旧大纲",
            "[0] 返回主菜单",
        ],
        "db": [
            "【小说档案库】",
            f"当前档案：{status.get('active_slot', '')}（{status.get('novel_title', '')}）",
            f"共 {status.get('slot_count', 0)} 个档案",
            "",
            "[1] 查看所有档案",
            "[2] 切换小说",
            "[3] 新建小说档案",
            "[0] 返回主菜单",
        ],
        "writing": [
            "【开始写作】",
            f"当前小说：{status.get('novel_title', '')}",
            f"当前章节数：{status.get('chapter_count', 0)} 章",
            f"当前字数：{status.get('total_words', 0):,} 字",
            "",
            "[1] 查看章节列表",
            "[2] 写新章节",
            "[3] 检查已写章节",
            "[0] 返回主菜单",
        ],
        "novice": [
            "【新手检查】",
            "我会检查以下项目：",
            "  · 项目是否初始化",
            "  · 数据库是否正常",
            "  · 小说档案库是否存在",
            "  · 是否有激活大纲",
            "  · 是否可以开写",
            "",
            "[1] 开始检查",
            "[0] 返回主菜单",
        ],
    }
    return "\n".join(menus.get(menu_type, ["未知菜单"]))
