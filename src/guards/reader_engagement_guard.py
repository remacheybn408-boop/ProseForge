#!/usr/bin/env python3
"""
reader_engagement_guard.py — L2 聚合门禁 v0.8.0

读者参与度：开篇、拉力、情感冲击、心理一致性。包含四个子检测：

- opening_hook: 开篇弱/强模式（前 1-5 行）
- reader_pull: 章尾悬念 / 微回报 / 新线索 / 酷时刻 / 上章回应
- emotional_impact: 情感词汇密度 / 情感曲线单一性
- character_psychology: 心理病理词汇密度 / 触发词一致性 / 极端情绪偏差

character_psychology 需要 project_root + character_name + genre，
通过 extra_context 透传。reader_pull 可选 previous_chapter_summary。
"""

from src.guards._cluster_aggregator import aggregate_cluster, safe_run
from src.guards.opening_hook_guard import run_opening_hook_check
from src.guards.reader_pull_guard import run_reader_pull_check
from src.guards.emotional_impact_guard import run_emotional_impact_check
from src.guards.human_texture.character_psychology_guard import (
    run_character_psychology_check,
)


def run_reader_engagement_check(content: str, chapter_no: int = 0,
                                 extra_context: dict = None) -> dict:
    extra_context = extra_context or {}
    prev_summary = extra_context.get("previous_chapter_summary")
    project_root = extra_context.get("project_root")
    character_name = extra_context.get("character_name")
    genre = extra_context.get("genre", "default")

    results = [
        safe_run("opening_hook_guard", run_opening_hook_check, content, chapter_no),
        safe_run(
            "reader_pull_guard", run_reader_pull_check,
            content, chapter_no, previous_chapter_summary=prev_summary,
        ),
        safe_run("emotional_impact_guard", run_emotional_impact_check, content, chapter_no),
        safe_run(
            "character_psychology_guard", run_character_psychology_check,
            content, chapter_no,
            project_root=project_root,
            character_name=character_name,
            genre=genre,
        ),
    ]
    return aggregate_cluster("reader_engagement_guard", results, chapter_no)
