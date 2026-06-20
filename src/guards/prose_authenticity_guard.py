#!/usr/bin/env python3
"""
prose_authenticity_guard.py — L2 聚合门禁 v0.8.0

文风真实感：防 AI 腔、防总结、视角一致。包含五个子检测：

- anti_ai: 9 类 AI 模式（解释腔 / 模板句 / 拟人 / 极端化 / 喉音开头 / 碎片化）
- show_dont_tell: 32 类 AI 总结腔（顿悟 / 命运 / 说教 / 望远镜）
- perplexity_quality: n-gram 惊讶度 / 模板短语比例 / 节奏平坦度 / 抽象具体比
- classical_register: 文言密度 / 古文块后无反应
- pov_consistency: 视角代词一致性 / 内心独白标记密度

perplexity_quality 需要 config + novel_slug，由 registry 通过 extra_context 透传；
缺这两项时跳过该子检测。
"""

from src.guards._cluster_aggregator import aggregate_cluster, safe_run
from src.guards.anti_ai_guard import run_anti_ai_check
from src.guards.show_dont_tell_guard import run_show_dont_tell_check
from src.guards.classical_register_guard import run_classical_register_check
from src.guards.pov_consistency_guard import run_pov_consistency_check


def _run_perplexity(content, chapter_no, extra_context):
    ctx = extra_context or {}
    if "perplexity_config" not in ctx or ctx.get("perplexity_config") is None:
        return {
            "guard": "perplexity_quality_guard",
            "status": "PASS",
            "score": 100,
            "note": "skipped (no perplexity_config in extra_context)",
        }
    cfg = ctx.get("perplexity_config") or {}
    slug = ctx.get("novel_slug", "default")
    from src.guards.perplexity_quality_guard import build_report
    return build_report(content, cfg, slug, chapter_no)


def run_prose_authenticity_check(content: str, chapter_no: int = 0,
                                  extra_context: dict = None) -> dict:
    extra_context = extra_context or {}
    vc = extra_context.get("voice_context", {}) or {}
    voice_profiles = vc.get("profiles")

    results = [
        safe_run("anti_ai_guard", run_anti_ai_check, content, chapter_no),
        safe_run("show_dont_tell_guard", run_show_dont_tell_check, content, chapter_no),
        safe_run("perplexity_quality_guard", _run_perplexity, content, chapter_no, extra_context),
        safe_run(
            "classical_register_guard", run_classical_register_check,
            content, chapter_no, voice_profiles=voice_profiles,
        ),
        safe_run("pov_consistency_guard", run_pov_consistency_check, content, chapter_no),
    ]
    return aggregate_cluster("prose_authenticity_guard", results, chapter_no)
