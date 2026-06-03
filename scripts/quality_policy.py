#!/usr/bin/env python3
"""
quality_policy.py — 质量策略配置 v0.4.0

定义门禁执行策略: 分层、置信度、双证据、短章保护、风格白名单。
不包含门禁逻辑，只提供策略查询和校验。

用法:
  from quality_policy import QualityPolicy
  qp = QualityPolicy(config)
  qp.can_fail("continuity_evidence_guard")  # True
  qp.can_fail("style_variation_guard")      # False
"""
from typing import Optional


DEFAULT_POLICY = {
    "version": "v0.4.0",
    "run_mode": "standard",
    "max_final_revision_tasks": 5,
    "min_warning_confidence": 0.55,
    "min_top_task_confidence": 0.70,
    "require_two_evidence_for_warning": True,
    "quality_guards_warning_only": True,
    "compliance_guard_can_block": True,
    "deduplicate_warnings": True,
    "skip_heavy_guards_for_short_chapters": True,
    "short_chapter_threshold_chars": 1000,
    "baseline_required_for_strong_warning": True,
}

DEFAULT_STYLE_ALLOWLIST = {
    "dialect_enabled": True,
    "classical_chinese_enabled": True,
    "character_catchphrase_enabled": True,
    "allowed_dialect_terms": [],
    "allowed_classical_terms": [],
    "character_voice_profiles": {},
}

# Level 1 guards: can FAIL (structural safety)
LEVEL1_GUARDS = {
    "continuity_evidence_guard", "canon_evidence_guard",
    "hallucination_guard", "scene_delta_guard",
}

# Level 2 guards: WARNING only (quality advice)
LEVEL2_GUARDS = {
    "anti_ai_guard", "padding_guard", "show_dont_tell_guard",
    "character_voice_guard", "dialogue_beat_guard", "classical_register_guard",
    "perplexity_quality_guard", "editor_revision_guard",
    "concrete_anchor_guard", "scene_causality_guard",
    "dialogue_naturalness_guard", "style_variation_guard",
}

# Level 3 guard: can BLOCK (compliance)
LEVEL3_GUARDS = {"compliance_selfcheck_guard"}


class QualityPolicy:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.policy = {**DEFAULT_POLICY, **cfg.get("quality_policy", {})}
        self.style_allowlist = {**DEFAULT_STYLE_ALLOWLIST,
                                **cfg.get("style_allowlist", {})}

    def can_fail(self, guard_name: str) -> bool:
        """该 guard 是否可以 FAIL"""
        return guard_name in LEVEL1_GUARDS

    def can_block(self, guard_name: str) -> bool:
        """该 guard 是否可以 BLOCK"""
        return guard_name in LEVEL3_GUARDS

    def is_warning_only(self, guard_name: str) -> bool:
        """该 guard 是否只能 WARNING"""
        return guard_name in LEVEL2_GUARDS

    def guard_level(self, guard_name: str) -> int:
        if guard_name in LEVEL1_GUARDS: return 1
        if guard_name in LEVEL2_GUARDS: return 2
        if guard_name in LEVEL3_GUARDS: return 3
        return 2  # default to quality advice

    def min_chars_for_full_guards(self) -> int:
        return self.policy.get("short_chapter_threshold_chars", 1000)

    def max_tasks(self) -> int:
        return self.policy.get("max_final_revision_tasks", 5)

    def min_confidence(self) -> float:
        return self.policy.get("min_warning_confidence", 0.55)

    def require_two_evidence(self) -> bool:
        return self.policy.get("require_two_evidence_for_warning", True)

    def deduplicate(self) -> bool:
        return self.policy.get("deduplicate_warnings", True)

    def is_dialect_allowed(self, term: str) -> bool:
        if not self.style_allowlist.get("dialect_enabled", True):
            return False
        allowed = self.style_allowlist.get("allowed_dialect_terms", [])
        return term in allowed if allowed else True

    def is_classical_allowed(self, term: str) -> bool:
        if not self.style_allowlist.get("classical_chinese_enabled", True):
            return False
        allowed = self.style_allowlist.get("allowed_classical_terms", [])
        return term in allowed if allowed else True

    def should_skip_heavy_for_chapter(self, word_count: int) -> bool:
        if not self.policy.get("skip_heavy_guards_for_short_chapters", True):
            return False
        return word_count < self.min_chars_for_full_guards()

    def to_dict(self) -> dict:
        return {
            "policy": self.policy,
            "style_allowlist": self.style_allowlist,
            "guard_levels": {
                "level1_can_fail": sorted(LEVEL1_GUARDS),
                "level2_warning_only": sorted(LEVEL2_GUARDS),
                "level3_can_block": sorted(LEVEL3_GUARDS),
            },
        }
