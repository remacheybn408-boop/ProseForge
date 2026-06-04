"""schemas.py — MCP 工具参数和返回结构定义。

为每个 MCP 工具定义输入参数、返回结果的格式说明。
这些定义主要用于工具描述，帮助 MCP 客户端理解如何调用。
"""

from typing import Optional, List, Dict, Any


# ── novel_menu ──
# 输入：无
# 返回：中文菜单字符串

# ── novel_status ──
NOVEL_STATUS_PARAMS = {
    "type": "object",
    "properties": {},
    "required": [],
    "description": "查看当前小说引擎状态，无需参数。",
}
# 返回：中文状态字符串

# ── novel_db_list ──
# 输入：无
# 返回：数据库列表字符串

# ── novel_outline_list ──
# 输入：无
# 返回：大纲列表字符串

# ── novel_outline_add ──
NOVEL_OUTLINE_ADD_PARAMS = {
    "outline_text": {
        "type": "string",
        "description": "大纲正文，纯文本格式",
        "required": True,
    },
    "title": {
        "type": "string",
        "description": "大纲标题（可选，不指定则自动生成）",
        "required": False,
    },
    "confirm_action": {
        "type": "boolean",
        "description": "是否确认执行（二次确认，防止误操作）",
        "required": False,
    },
}

# ── novel_chapters ──
# 输入：无
# 返回：章节列表字符串

# ── novel_agents_review ──
NOVEL_AGENTS_REVIEW_PARAMS = {
    "chapter": {
        "type": "integer",
        "description": "章节号，如 1 表示第 1 章",
        "required": True,
    },
    "mode": {
        "type": "string",
        "enum": ["light", "full"],
        "description": "审稿模式：light 轻量（快速），full 完整（详细）",
        "required": False,
        "default": "light",
    },
}

# ── novel_story_health ──
# 输入：无
# 返回：Story Contract 健康状态字符串

# ── novel_report ──
# 输入：无
# 返回：最近报告字符串

# ── novel_export_txt ──
NOVEL_EXPORT_PARAMS = {
    "slug": {
        "type": "string",
        "description": "小说标识 slug（可选，默认当前小说）",
        "required": False,
    },
    "format": {
        "type": "string",
        "enum": ["txt", "md"],
        "description": "导出格式：txt 纯文本 / md Markdown",
        "required": False,
        "default": "txt",
    },
}
