"""command_runner.py — 安全执行 novel.py 命令

统一调用 novel.py 命令的入口。
负责超时、错误捕获、输出清理、返回中文摘要。
不暴露终端命令、路径、traceback 给普通用户。
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

from .safety import (
    PROJECT_ROOT,
    is_allowed_command,
    SAFE_ERROR_MESSAGES,
)


# ── 各工具的超时设置（秒） ──
TIMEOUTS = {
    "status": 10,
    "board": 10,
    "db list": 10,
    "db current": 10,
    "db info": 10,
    "outline list": 10,
    "outline current": 10,
    "chapters": 10,
    "report": 20,
    "guards": 10,
    "agents review": 60,
    "jury": 60,
    "export": 60,
    "story health": 10,
    "voice list": 10,
    "character list": 10,
    "genre list": 10,
    "style list": 10,
    "rag status": 10,
    "stability-check": 300,
    "default": 30,
}


def _get_timeout(cmd_str: str) -> int:
    """获取命令的超时时间。"""
    for prefix, timeout in TIMEOUTS.items():
        if cmd_str.startswith(prefix):
            return timeout
    return TIMEOUTS["default"]


def _clean_output(output: str) -> str:
    """清理命令输出，移除多余的空行和调试信息。

    保留中文内容，移除 traceback 等。
    """
    lines = output.split("\n")
    cleaned = []
    skip_traceback = False
    for line in lines:
        if line.startswith("Traceback"):
            skip_traceback = True
            continue
        if skip_traceback:
            if line.strip() == "" or line.startswith(" ") or line.startswith("\t"):
                continue
            skip_traceback = False
        # Filter out command echo from demo
        if line.strip().startswith("$ python novel.py"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def run_command(cmd_str: str) -> Tuple[bool, str, Optional[int]]:
    """安全执行 novel.py 命令。

    参数：
        cmd_str: 命令字符串，如 "status"、"db list"

    返回：
        (success, output_or_error_message, exit_code)
        success: True 表示执行成功
        output_or_error_message: 命令输出或中文错误信息
        exit_code: 进程退出码，None 表示超时或未执行
    """
    if not is_allowed_command(cmd_str):
        return False, SAFE_ERROR_MESSAGES["not_allowed"], None

    timeout = _get_timeout(cmd_str)
    novel_py = PROJECT_ROOT / "novel.py"
    python_exe = sys.executable

    try:
        start = time.time()
        result = subprocess.run(
            [python_exe, str(novel_py)] + cmd_str.split(),
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = (time.time() - start) * 1000

        output = result.stdout + result.stderr
        cleaned = _clean_output(output)

        if result.returncode == 0:
            return True, cleaned, 0
        else:
            # 检查是否是 import error
            if "ModuleNotFoundError" in output or "ImportError" in output:
                return False, SAFE_ERROR_MESSAGES["import_error"], result.returncode
            if cleaned:
                return False, cleaned, result.returncode
            return False, SAFE_ERROR_MESSAGES["execution_failed"], result.returncode

    except subprocess.TimeoutExpired:
        return False, SAFE_ERROR_MESSAGES["timeout"], None
    except Exception as e:
        return False, SAFE_ERROR_MESSAGES["unknown"], None
