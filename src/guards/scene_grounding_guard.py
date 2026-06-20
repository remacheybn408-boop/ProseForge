#!/usr/bin/env python3
"""
scene_grounding_guard.py — L2 聚合门禁 v0.8.0

场景具象化：检查场景是否站得住。包含三个子检测：

- concrete_anchor: 物件/动作/场景锚点覆盖率（500 字滑窗）
- sensory_detail: 五感维度密度分布
- scene_causality: 因果链元素（Cause/Action/Resistance/Cost/Result/Hook）

共享依赖：utils.sensory_lexicon + utils.consequence_lexicon
"""

from src.guards._cluster_aggregator import aggregate_cluster, safe_run
from src.guards.concrete_anchor_guard import run_concrete_anchor_check
from src.guards.sensory_detail_guard import run_sensory_detail_check
from src.guards.scene_causality_guard import run_scene_causality_check


def run_scene_grounding_check(content: str, chapter_no: int = 0) -> dict:
    """对外入口。registry 默认按 (content, chapter_no) 签名调用。"""
    results = [
        safe_run("concrete_anchor_guard", run_concrete_anchor_check, content, chapter_no),
        safe_run("sensory_detail_guard", run_sensory_detail_check, content, chapter_no),
        safe_run("scene_causality_guard", run_scene_causality_check, content, chapter_no),
    ]
    return aggregate_cluster("scene_grounding_guard", results, chapter_no)
