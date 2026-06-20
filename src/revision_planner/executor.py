"""executor.py — MVP 执行器：按 list[Action] 改写 text。

执行规则：
- actions 应已按 char_start 倒序排好（planner 输出即如此）
- 倒序应用避免后续 offset 漂移
- 单 action 失败（如 original 不匹配）跳过该 action，记录到 log，其他继续
- 返回 (new_text, log)
"""
from __future__ import annotations
from typing import Any

from .action import Action, OP_REPLACE, OP_DELETE


def execute(actions: list[Action], text: str) -> tuple[str, list[dict[str, Any]]]:
    """按倒序应用 actions，返回新文本和每个 action 的执行日志。"""
    # 防御：调用方可能未排序，这里强制倒序
    ordered = sorted(actions, key=lambda a: a.location.char_start, reverse=True)
    new_text = text
    log: list[dict[str, Any]] = []

    for action in ordered:
        start = action.location.char_start
        end = action.location.char_end
        if start is None or end is None:
            log.append({"action": action.to_dict(), "status": "skipped",
                        "reason": "no char offset"})
            continue
        if start < 0 or end > len(new_text) or start >= end:
            log.append({"action": action.to_dict(), "status": "skipped",
                        "reason": f"invalid span [{start}, {end}) for len {len(new_text)}"})
            continue

        actual = new_text[start:end]
        expected = action.args.get("original", "")
        if expected and actual != expected:
            log.append({"action": action.to_dict(), "status": "skipped",
                        "reason": f"original mismatch: expected {expected!r}, got {actual!r}"})
            continue

        if action.op == OP_REPLACE:
            replacement = action.args.get("replacement", "")
            new_text = new_text[:start] + replacement + new_text[end:]
            log.append({"action": action.to_dict(), "status": "applied",
                        "before": actual, "after": replacement})
        elif action.op == OP_DELETE:
            new_text = new_text[:start] + new_text[end:]
            log.append({"action": action.to_dict(), "status": "applied",
                        "before": actual, "after": ""})
        else:
            log.append({"action": action.to_dict(), "status": "skipped",
                        "reason": f"unknown op {action.op}"})

    return new_text, log
