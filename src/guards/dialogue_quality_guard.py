#!/usr/bin/env python3
"""
dialogue_quality_guard.py — L2 聚合门禁 v0.8.0

对话与角色声纹：包含四个子检测：

- dialogue_beat: 对白节拍完整性（动作/停顿/误会/代价）
- dialogue_structure: 对白结构（打断/未完成句/称呼变化/句长 CV）
- character_voice: 角色声纹（方言/梗/英语密度 + 旁白污染）
- meme_pack: 梗密度 + 严肃场景梗滥用 + 方言密度

声纹相关子检测需要 voice_profiles/voice_packs/narration_policy，
由 registry 通过 extra_context.voice_context 透传。
"""

from src.guards._cluster_aggregator import aggregate_cluster, safe_run
from src.guards.dialogue_beat_guard import run_dialogue_beat_check
from src.guards.dialogue_structure_guard import run_dialogue_structure_check
from src.guards.character_voice_guard import run_character_voice_check
from src.guards.meme_pack_guard import run_meme_pack_check


def run_dialogue_quality_check(content: str, chapter_no: int = 0,
                                extra_context: dict = None) -> dict:
    extra_context = extra_context or {}
    vc = extra_context.get("voice_context", {}) or {}
    voice_profiles = vc.get("profiles")
    voice_packs = vc.get("packs")
    narration_policy = vc.get("narration_policy")
    meme_packs_dir = extra_context.get("meme_packs_dir")
    dialect_packs = extra_context.get("dialect_packs")

    results = [
        safe_run("dialogue_beat_guard", run_dialogue_beat_check, content, chapter_no),
        safe_run("dialogue_structure_guard", run_dialogue_structure_check, content, chapter_no),
        safe_run(
            "character_voice_guard", run_character_voice_check,
            content, chapter_no,
            voice_profiles=voice_profiles,
            voice_packs=voice_packs,
            narration_policy=narration_policy,
        ),
        safe_run(
            "meme_pack_guard", run_meme_pack_check,
            content, chapter_no,
            voice_profiles=voice_profiles,
            meme_packs_dir=meme_packs_dir,
            dialect_packs=dialect_packs,
        ),
    ]
    return aggregate_cluster("dialogue_quality_guard", results, chapter_no)
