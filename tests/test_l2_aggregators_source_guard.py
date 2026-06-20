"""Source-guard propagation tests for the five L2 aggregator guards.

AGENTS.md#H8: 间接冒烟（`test_guard_entry_consistency.py`）证明 5 个聚合都跑得
通，但没断言 `GuardFinding.source_guard` 真的被 `_cluster_aggregator` →
`_adapt_legacy_dict` 这条链准确填充。本文件用真实入口输出（不是 mock raw dict）
把链尾守住。

Protocol chain：
    run_<cluster>_check(text, ...) →
        每子检测 dict 经 _cluster_aggregator.safe_run 标 `source=<sub>` →
            aggregate_cluster 聚合 flags →
                _adapt_legacy_dict 把 flag["source"] 翻成 finding.source_guard

关联：`src/guards/_cluster_aggregator.py:104/110`，
`src/guards/guard_registry.py:130`（_adapt_legacy_dict 写 source_guard）。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.guards.dialogue_quality_guard import run_dialogue_quality_check
from src.guards.guard_registry import _adapt_legacy_dict
from src.guards.narrative_rhythm_guard import run_narrative_rhythm_check
from src.guards.prose_authenticity_guard import run_prose_authenticity_check
from src.guards.reader_engagement_guard import run_reader_engagement_check
from src.guards.scene_grounding_guard import run_scene_grounding_check


# 一段刻意"AI 味"的文本：抽象总结多、感官锚点少、对白无节拍、开头平淡、
# 句开重复。设计目的是尽可能让 5 个聚合的多数子检测都产出 finding，
# 这样 source_guard 链的覆盖面更大。
SAMPLE_TEXT = """她突然意识到，命运总是这样捉弄人。生活的本质或许就是不断的妥协与挣扎。
她开始反思自己的人生，觉得一切都是那么的虚无缥缈，仿佛一场盛大的幻梦。
"你还好吗？"他问。
"没事，"她说。
"真的没事吗？"
"嗯。"
她不禁想起了过去的种种，那些遗憾、那些错过、那些来不及说出口的话。
她终于明白了，原来人生就是一场漫长的告别。
他望着她，心中涌起无限的感慨。这一刻，他明白了爱与失去的真谛。
天地之大，何处可栖。子曰：逝者如斯夫。她想起了这句古话。
她哭了。她笑了。她的内心五味杂陈。
他们就这样静静地坐着，谁也没有说话，时间仿佛凝固了一般。
她觉得自己终于成长了，明白了什么是真正的爱与责任。
故事还在继续，但她已经不再是那个懵懂的少女了。"""


CASES = [
    pytest.param(
        "scene_grounding_guard",
        lambda: run_scene_grounding_check(SAMPLE_TEXT, chapter_no=1),
        {"concrete_anchor_guard", "sensory_detail_guard", "scene_causality_guard"},
        id="scene_grounding",
    ),
    pytest.param(
        "narrative_rhythm_guard",
        lambda: run_narrative_rhythm_check(SAMPLE_TEXT, chapter_no=1),
        {
            "style_variation_guard", "pacing_variation_guard", "padding_guard",
            "punctuation_guard", "editor_revision_guard",
        },
        id="narrative_rhythm",
    ),
    pytest.param(
        "dialogue_quality_guard",
        lambda: run_dialogue_quality_check(SAMPLE_TEXT, chapter_no=1, extra_context={}),
        {
            "dialogue_beat_guard", "dialogue_structure_guard",
            "character_voice_guard", "meme_pack_guard",
        },
        id="dialogue_quality",
    ),
    pytest.param(
        "prose_authenticity_guard",
        lambda: run_prose_authenticity_check(
            SAMPLE_TEXT, chapter_no=1,
            extra_context={"perplexity_config": {}, "novel_slug": "_test"},
        ),
        {
            "anti_ai_guard", "show_dont_tell_guard", "perplexity_quality_guard",
            "classical_register_guard", "pov_consistency_guard",
        },
        id="prose_authenticity",
    ),
    pytest.param(
        "reader_engagement_guard",
        lambda: run_reader_engagement_check(
            SAMPLE_TEXT, chapter_no=1,
            extra_context={
                "project_root": str(Path(__file__).resolve().parent.parent),
                "character_name": "",
                "genre": "default",
            },
        ),
        {
            "opening_hook_guard", "reader_pull_guard",
            "emotional_impact_guard", "character_psychology_guard",
        },
        id="reader_engagement",
    ),
]


@pytest.mark.parametrize("parent_name, run_entry, legal_subs", CASES)
def test_l2_aggregator_preserves_source_guard(parent_name, run_entry, legal_subs):
    """每个 L2 聚合：每条 finding 必须填了合法子检测名做 source_guard。"""
    raw = run_entry()
    assert isinstance(raw, dict), f"{parent_name} 没返回 dict"
    assert raw.get("guard") == parent_name

    result = _adapt_legacy_dict(parent_name, raw)
    assert result.guard == parent_name

    # 子检测身份必须出现在 sub_statuses（聚合器自己的健康检查）
    sub_statuses = raw.get("sub_statuses", {})
    assert set(sub_statuses).issubset(legal_subs), (
        f"{parent_name} sub_statuses 出现意外子检测: "
        f"{set(sub_statuses) - legal_subs}"
    )

    # 核心断言：所有 finding 的 source_guard 必须落在合法子集
    # （或为空 — 仅当 finding 来自 status 兜底，没有原始 source）
    bad = [
        f for f in result.findings
        if f.source_guard and f.source_guard not in legal_subs
    ]
    assert not bad, (
        f"{parent_name} 出现非法 source_guard: "
        f"{[(f.code, f.source_guard) for f in bad]}"
    )

    # 至少一条 finding 必须有 source_guard 落在合法子集
    # （证明 _cluster_aggregator → _adapt_legacy_dict 链端到端可用）
    matched = [f for f in result.findings if f.source_guard in legal_subs]
    assert matched, (
        f"{parent_name} 所有 finding 的 source_guard 都是空 — "
        f"说明子检测身份没传到 adapter。findings={len(result.findings)}, "
        f"raw flags={len(raw.get('flags', []))}, "
        f"raw issues={len(raw.get('issues', []))}"
    )


def test_adapter_finding_guard_field_is_parent():
    """finding.guard 应是父聚合名（v0.8.0 协议），不是子检测名。"""
    raw = run_scene_grounding_check(SAMPLE_TEXT, chapter_no=1)
    result = _adapt_legacy_dict("scene_grounding_guard", raw)
    for f in result.findings:
        assert f.guard == "scene_grounding_guard", (
            f"finding.guard 应是父名，实为 {f.guard}"
        )
