#!/usr/bin/env python3
"""
narrative_rhythm_guard.py — L2 聚合门禁 v0.8.0

文字节奏与水分：检查叙述节奏的变化度，及凑字数痕迹。包含五个子检测：

- style_variation: 句开重复、句长 CV、转折词密度
- pacing_variation: 段落长度 CV、动作/对话/描写比例、紧张标记
- padding: 空转心理、对话回声、章尾灌水（5 类）
- punctuation: 破折号/省略号/感叹号密度与分布
- editor_revision: 段落节奏 CV、过度解释段落

共享依赖：utils.text_metrics（length_cv / repeated_phrase_ratio）
"""

from src.guards._cluster_aggregator import aggregate_cluster, safe_run
from src.guards.style_variation_guard import build_report as run_style_variation
from src.guards.pacing_variation_guard import run_pacing_variation_check
from src.guards.padding_guard import run_padding_check
from src.guards.punctuation_guard import run_punctuation_check
from src.guards.editor_revision_guard import run_editor_revision_check


def run_narrative_rhythm_check(content: str, chapter_no: int = 0,
                                chapter_type: str = "normal") -> dict:
    """对外入口。padding 需要 chapter_type，从 extra_context 由 registry 透传。"""
    results = [
        safe_run("style_variation_guard", run_style_variation, content, chapter_no),
        safe_run("pacing_variation_guard", run_pacing_variation_check, content, chapter_no),
        safe_run("padding_guard", run_padding_check, content, chapter_type),
        safe_run("punctuation_guard", run_punctuation_check, content, chapter_no),
        safe_run("editor_revision_guard", run_editor_revision_check, content, chapter_no),
    ]
    return aggregate_cluster("narrative_rhythm_guard", results, chapter_no)
