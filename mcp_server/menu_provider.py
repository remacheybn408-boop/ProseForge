"""menu_provider.py — 中文菜单生成器

生成小说引擎中文菜单，展示当前项目状态和可用操作。
优先读取 configs/scc_menu.json，内置备用菜单。
不暴露终端命令。
"""

import json
from pathlib import Path
from typing import Optional

from .command_runner import run_command

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCC_MENU_PATH = PROJECT_ROOT / "configs" / "scc_menu.json"


def _load_status() -> dict:
    """获取当前项目状态。"""
    success, output, _ = run_command("status")
    status = {
        "version": "v0.6.7",
        "initialized": False,
        "active_slot": "",
        "novel_title": "",
        "outline_active": False,
        "chapter_count": 0,
        "db_ok": False,
    }

    if success:
        status["initialized"] = True
        for line in output.split("\n"):
            line = line.strip()
            if "ALL PASS" in line or "OK" in line:
                status["initialized"] = True
        # Try to parse key status items
        for line in output.split("\n"):
            if "SQLite DB" in line and "[OK]" in line:
                status["db_ok"] = True

    # Try to get active slot info from workspace registry
    try:
        ws_reg = PROJECT_ROOT / "workspace" / "registry.json"
        if ws_reg.exists():
            reg = json.loads(ws_reg.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            if active:
                status["active_slot"] = active
                slot_dir = PROJECT_ROOT / "workspace" / active
                db_path = slot_dir / "novel.db"
                if db_path.exists():
                    import sqlite3
                    try:
                        conn = sqlite3.connect(str(db_path))
                        row = conn.execute("SELECT title FROM novels LIMIT 1").fetchone()
                        if row:
                            status["novel_title"] = row[0]
                        ch = conn.execute("SELECT COUNT(*) FROM chapters").fetchone()
                        if ch:
                            status["chapter_count"] = ch[0]
                        conn.close()
                    except Exception:
                        pass
    except Exception:
        pass

    return status


def render_main_menu() -> str:
    """生成主菜单（中文纯文本）。"""
    status = _load_status()

    lines = []
    lines.append("=" * 56)
    lines.append(f"  小说引擎 {status.get('version', 'v0.6.7')} — 中文菜单")
    lines.append("=" * 56)
    lines.append("")

    # 项目状态
    if status["initialized"]:
        if status["novel_title"]:
            lines.append(f"  📖 当前小说：{status['novel_title']}")
            lines.append(f"  📂 当前档案：{status['active_slot']}")
            lines.append(f"  📝 章节数量：{status['chapter_count']} 章")
            if status["chapter_count"] > 0:
                lines.append("  ✅ 当前状态：可以继续写作或审稿")
            else:
                lines.append("  ✅ 当前状态：可以开始写作")
        else:
            lines.append("  📂 项目已初始化，还没有小说")
            lines.append("  💡 推荐：先添加大纲，自动创建小说项目")
    else:
        lines.append("  ⚠️  项目尚未初始化")
        lines.append("  💡 推荐：选择 1，完成新手检查")

    lines.append("")
    lines.append("  ─" * 18)
    lines.append("  请选择：")
    lines.append("  ─" * 18)
    lines.append("  [1] 新手检查     环境诊断 & 项目初始化")
    lines.append("  [2] 小说档案库   查看/切换/创建小说工作区")
    lines.append("  [3] 大纲管理     查看/添加大纲版本")
    lines.append("  [4] 开始写作     写前任务卡 → 写作 → 检查")
    lines.append("  [5] Agent 审稿     AI 审稿团（轻量/完整）")
    lines.append("  [6] Story Contract  章节合同与健康检查")
    lines.append("  [7] 报告与导出   查看报告 & 导出小说")
    lines.append("  [8] 角色管理     声纹卡 & 角色卡")
    lines.append("  [9] 其他功能     题材/风格/RAG/项目看板")
    lines.append("  [0] 退出")
    lines.append("")
    lines.append("  💬 你也可以直接说：")
    lines.append("   「添加大纲」「写第一章」「审稿」「导出 TXT」")
    lines.append("   「查看状态」「有哪些小说」「故事链健康」")
    lines.append("")

    return "\n".join(lines)


def render_status_text(output: str) -> str:
    """将 status 命令输出转为更友好的中文格式。"""
    # 直接返回清洗后的输出，已经去掉了 traceback
    return output


def render_chapter_list(chapters_output: str) -> str:
    """将 chapters 命令输出转为中文格式。"""
    if not chapters_output or chapters_output.strip() == "":
        return "当前没有章节数据。"
    return chapters_output
