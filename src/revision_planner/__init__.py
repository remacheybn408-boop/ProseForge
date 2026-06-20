"""revision_planner — 统一改写规划器。

正在建设中。当前进度：
  ✅ Step 0: detector finding 统一 schema  (schema.py)
  ⬜ Step 1: 5 个核心 detector 的 adapter
  ⬜ Step 2: planner MVP（聚合 + 排序 + 冲突解决）
  ⬜ Step 3: executor MVP（按 Layer 1 原语执行）
  ⬜ Step 4: 与 post.py 集成

设计动机见 git log，关键决定见 schema.py 的 docstring。
"""
from .schema import Finding, Severity, TextSpan  # noqa: F401
