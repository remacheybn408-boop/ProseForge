#!/usr/bin/env python3
"""
guard_orchestrator.py — 门禁调度器（thin wrapper）

v0.4.5+：所有门禁执行逻辑统一搬到 `src.guards.guard_registry`。
本文件保留 `run_orchestrated()` 旧入口，调用方继续走这里就行。

v0.8.0：原本散落在这里的 GUARD_LEVELS / MODE_GUARDS / GUARD_RUNNERS / run_guard
全部下线 — registry 是唯一真源。如果你看到旧 import，请改 `src.guards.guard_registry`。
"""
from typing import Optional


def run_orchestrated(content: str, chapter_no: int, mode: str = "standard",
                     prev_tail: str = "", prev_brief: Optional[dict] = None,
                     config: Optional[dict] = None,
                     custom_guards: Optional[list] = None,
                     reports_dir: str = "",
                     extra_context: Optional[dict] = None,
                     chapter_type: str = "normal") -> dict:
    """
    Orchestrate all guards — thin wrapper around guard_registry.

    All guard execution logic lives in `src.guards.guard_registry`.
    """
    from src.guards.guard_registry import run_orchestrated as _run
    return _run(content, chapter_no, mode=mode,
                prev_tail=prev_tail, prev_brief=prev_brief,
                config=config, custom_guards=custom_guards,
                reports_dir=reports_dir, extra_context=extra_context,
                chapter_type=chapter_type)
