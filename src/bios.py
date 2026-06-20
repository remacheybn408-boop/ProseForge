#!/usr/bin/env python3
"""Deprecated compatibility shim for retired src.bios entrypoints."""

from __future__ import annotations


def execute(workflow, **kwargs):
    raise RuntimeError(
        "src.bios has been retired. Call explicit entrypoints instead: "
        "src.pipeline.pre.run_pre, src.pipeline.post.run_post, "
        "src.pipeline.volume.volume_post, or src.agents.orchestrator.run_agent_review."
    )
