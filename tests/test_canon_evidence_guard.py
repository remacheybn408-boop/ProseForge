"""
test_canon_evidence_guard.py — 防幻觉来源证据门禁测试
"""
import pytest, json, sys, os
from src.guards.canon_evidence_guard import run_canon_evidence_check


class TestCanonEvidencePass:
    def test_no_hard_claims_passes(self):
        """没有硬事实声明的文本应该通过"""
        content = "清晨。他站在院子里，望着远处的山。\n这是平凡的一天。"
        report, claims = run_canon_evidence_check(content, 5)
        assert report["status"] == "PASS"
        assert report["evidence_coverage"] == 1.0

    def test_task_card_allowed_passes(self):
        """task_card 允许的新设定应通过"""
        content = "他领悟了灵频呼吸法，这是全新的修炼方法。"
        task_card = {"allowed_new_canon": ["灵频呼吸法", "修炼方法"]}
        report, claims = run_canon_evidence_check(content, 5, task_card=task_card)
        assert report["allowed_new_canon_count"] >= 1
        assert report["hard_claims_without_source"] == 0

    def test_soft_detail_passes(self):
        """软细节不拦截"""
        content = "他的左臂受了伤，血流不止。\"帮我一下。\"他说。"
        report, claims = run_canon_evidence_check(content, 5)
        # injury/location state are treated as soft_detail
        assert report["status"] == "PASS"


class TestCanonEvidenceFail:
    def test_unsupported_realm_shift(self):
        """无来源的境界突破应被拦截"""
        content = "他突破境界，踏入元婴层次。从此天下无敌。"
        report, claims = run_canon_evidence_check(content, 5)
        # Without task_card allowance, realm shift should be unsupported
        assert report["hard_claims_without_source"] > 0
        assert report["evidence_coverage"] < 1.0

    def test_unsupported_faction_appearance(self):
        """无来源的新势力出现应被拦截"""
        content = "从未听过的幽冥教派突然出现，席卷了整个大陆。"
        report, claims = run_canon_evidence_check(content, 5)
        unsupported = report.get("unsupported_claims", [])
        assert len(unsupported) > 0

    def test_new_power_without_source(self):
        """无来源的新能力应被拦截"""
        content = "他获得了前所未有的神通——可以看穿一切伪装。"
        report, claims = run_canon_evidence_check(content, 5)
        assert report["hard_claims_without_source"] > 0
