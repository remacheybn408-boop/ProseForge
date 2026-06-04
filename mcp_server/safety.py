"""safety.py — MCP 安全白名单和规则

定义允许运行的 novel.py 命令、禁止的操作、项目目录边界。
所有 MCP 工具必须通过白名单检查才能执行。
"""

import re
from pathlib import Path

# ── 项目根目录 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 允许访问的目录（项目内） ──
ALLOWED_DIRS = [
    PROJECT_ROOT / "workspace",
    PROJECT_ROOT / "exports",
    PROJECT_ROOT / "reports",
    PROJECT_ROOT / "logs",
    PROJECT_ROOT / "configs",
    PROJECT_ROOT / "docs",
    PROJECT_ROOT / "examples",
    PROJECT_ROOT / "novels",
]

# ── 白名单命令模板 ──
# (command_args_pattern, description)
ALLOWED_COMMANDS = [
    # 状态和诊断
    (r"^status$", "环境诊断"),
    (r"^status --detail$", "详细诊断"),
    (r"^board$", "项目看板"),
    (r"^stability-check$", "稳定性检查"),
    (r"^stability-check --full$", "完整稳定性检查"),

    # 数据库管理（只读）
    (r"^db list$", "列出数据库 slot"),
    (r"^db current$", "显示当前 slot"),
    (r"^db info$", "显示 slot 详细信息"),
    (r"^db backup$", "备份当前 slot"),

    # 大纲管理（只读 + 安全的写操作）
    (r"^outline list$", "列出大纲"),
    (r"^outline current$", "显示当前大纲"),

    # 章节
    (r"^chapters$", "列出章节"),

    # 审稿
    (r"^agents review \d+ --mode light$", "轻量审稿"),
    (r"^agents review \d+ --mode full$", "完整审稿"),
    (r"^jury \d+$", "轻量审稿快捷命令"),

    # 报告和导出
    (r"^report$", "显示报告"),
    (r"^guards$", "列出守卫"),
    (r"^export --format txt$", "导出 TXT"),
    (r"^export --format md$", "导出 Markdown"),

    # Story Contract（只读）
    (r"^story health$", "故事链健康检查"),
    (r"^story contract \d+$", "生成章节合同"),
    (r"^story commit \d+$", "生成章节提交记录"),

    # 角色管理（只读）
    (r"^voice list$", "列出声纹卡"),
    (r"^character list$", "列出角色卡"),
    (r"^character show \S+$", "查看角色卡"),

    # 题材/风格（只读）
    (r"^genre list$", "列出题材包"),
    (r"^genre show \S+$", "查看题材包"),
    (r"^style list$", "列出风格包"),
    (r"^style show \S+$", "查看风格包"),

    # RAG（只读）
    (r"^rag status$", "RAG 状态"),

    # 新增——安全的大纲添加
    (r"^outline add--dry-run--title \S+$", "大纲添加预览（干运行）"),
]


def is_allowed_command(cmd_str: str) -> bool:
    """检查命令字符串是否在白名单内。"""
    cmd_str = cmd_str.strip()
    for pattern, _ in ALLOWED_COMMANDS:
        if re.fullmatch(pattern, cmd_str):
            return True
    return False


def is_path_safe(file_path: str) -> bool:
    """检查文件路径是否在允许的目录内。"""
    try:
        p = Path(file_path).resolve()
        for allowed in ALLOWED_DIRS:
            try:
                p.relative_to(allowed.resolve())
                return True
            except ValueError:
                continue
        return False
    except Exception:
        return False


# ── 禁止的关键词（用于输入过滤） ──
FORBIDDEN_KEYWORDS = [
    "rm ", "del ", "rmdir", "rd ", "format",
    "shell=True", "subprocess", "os.system",
    "eval(", "exec(", "__import__",
    "ssh ", "scp ", "curl ", "wget ",
    "> ", "| ", "&&", "||", ";",
]


def contains_forbidden(content: str) -> bool:
    """检查输入是否包含禁止关键词。"""
    lower = content.lower()
    for kw in FORBIDDEN_KEYWORDS:
        if kw.lower() in lower:
            return True
    return False


# ── 错误信息（安全的中文摘要，不暴露技术细节） ──
SAFE_ERROR_MESSAGES = {
    "timeout": "操作超时，已停止执行。建议先运行「查看状态」，确认项目是否正常。",
    "not_allowed": "当前 MCP 版本暂不支持此操作。如需帮助，请回复「菜单」查看可用功能。",
    "path_forbidden": "不允许访问此路径。MCP 只能读取项目内的文件。",
    "execution_failed": "操作执行失败。建议先运行「查看状态」，确认引擎是否正常加载。",
    "import_error": "执行失败：引擎模块未正确加载。建议运行稳定性检查，或检查发布包是否完整。",
    "unknown": "发生未知错误。建议先运行「查看状态」，确认项目是否正常。",
    "not_initialized": "项目尚未初始化。请先运行「菜单」，选择「新手检查」完成初始化。",
}
