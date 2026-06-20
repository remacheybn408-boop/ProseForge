"""action.py — planner 输出的可执行操作描述。

Action 是 planner 的输出 / executor 的输入，应是**完全可执行**的：
- 包含确切的字符位置（char_start/char_end）
- 包含确切的替换内容
- 包含追溯信息（source_findings 是哪些 Finding 触发的）

executor 不再做任何决策，只机械执行。
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

from .schema import TextSpan


# 当前支持的 op 类型
OP_REPLACE = "replace_phrase"
OP_DELETE = "delete_phrase"


@dataclass
class Action:
    """planner 输出的一个改写操作。

    Attributes:
        op: 操作类型，例如 OP_REPLACE / OP_DELETE。
        location: 必须包含 char_start/char_end 的精确位置。
        args: op 相关参数。OP_REPLACE 需要 {original, replacement}。
        source_findings: 触发本 action 的 Finding code 列表（追溯用）。
        reason: 人类可读的改动原因（调试 / 日志）。
    """
    op: str
    location: TextSpan
    args: dict[str, Any] = field(default_factory=dict)
    source_findings: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "op": self.op,
            "location": {
                "paragraph_idx": self.location.paragraph_idx,
                "char_start": self.location.char_start,
                "char_end": self.location.char_end,
            },
            "args": self.args,
            "source_findings": self.source_findings,
            "reason": self.reason,
        }
