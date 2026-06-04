"""audit.py — MCP 调用审计日志

记录所有 MCP 工具调用到 logs/mcp_audit.log。
不记录大纲全文、小说全文、用户隐私路径。
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "mcp_audit.log"


def _ensure_log_dir():
    _LOG_DIR.mkdir(parents=True, exist_ok=True)


def _get_logger() -> logging.Logger:
    """获取 MCP 审计日志记录器。"""
    _ensure_log_dir()
    logger = logging.getLogger("mcp_audit")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(str(_LOG_FILE), encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        logger.addHandler(handler)

    return logger


def log_call(
    tool_name: str,
    params: dict,
    success: bool,
    exit_code: Optional[int] = None,
    duration_ms: Optional[float] = None,
    error: Optional[str] = None,
):
    """记录一次 MCP 工具调用。

    参数：
        tool_name: 工具名，如 novel_menu
        params: 参数字典（只记录摘要，不记录全文）
        success: 是否成功
        exit_code: 进程退出码
        duration_ms: 耗时毫秒
        error: 错误摘要（不记录完整 traceback）
    """
    safe_params = {}
    for k, v in params.items():
        if isinstance(v, str) and len(v) > 100:
            safe_params[k] = v[:100] + "..."
        else:
            safe_params[k] = v

    record = {
        "tool": tool_name,
        "params": safe_params,
        "success": success,
        "exit_code": exit_code,
        "duration_ms": round(duration_ms, 1) if duration_ms is not None else None,
        "error": error[:200] if error else None,
    }

    logger = _get_logger()
    logger.info(json.dumps(record, ensure_ascii=False))
