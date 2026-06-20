"""
test_hallucination_guard.py — 幻觉拦截测试
"""
import pytest, json, sys, os
from src.guards.hallucination_guard import run_hallucination_check


class TestHallucinationPass:
    def test_clean_text_passes(self):
        """Normal text with no hallucinations should PASS."""
        text = "清晨。他站在院子里，望着远处的山。\n这是平凡的一天。\n"
        report = run_hallucination_check(text, 5)
        assert report["status"] == "PASS"

    def test_allowed_new_canon_passes(self):
        """New canon allowed by task card should PASS."""
        text = "他领悟了新的修炼方法——灵频呼吸法。"
        task_card = {"allowed_new_canon": ["灵频呼吸法", "修炼方法"]}
        report = run_hallucination_check(text, 5, task_card=task_card)
        assert report["status"] == "PASS"
        # Should have an allowed_new_canon entry
        allowed = [f for f in report.get("new_canon_items", []) if f["allowed"]]
        assert len(allowed) >= 1


class TestHallucinationFail:
    def test_realm_shift_blocked(self):
        """Sudden realm breakthrough should be flagged."""
        text = "他突破境界，踏入元婴层次。从此天下无敌。"
        report = run_hallucination_check(text, 5)
        blocked = report.get("blocked_items", [])
        assert len(blocked) >= 1

    def test_relation_shift_blocked(self):
        """Sudden relation change should be flagged."""
        text = "她忽然爱上了这个陌生人，心中涌起前所未有的情感。"
        report = run_hallucination_check(text, 3)
        blocked = report.get("blocked_items", [])
        assert len(blocked) >= 1

    def test_unauthorized_canon_flagged(self):
        """Unauthorized new faction should be flagged as unsupported."""
        text = "从未听过的幽冥教派突然出现，席卷了整个大陆。"
        report = run_hallucination_check(text, 5)
        unsupported = report.get("unsupported_claims", [])
        assert len(unsupported) >= 1

    def test_forgotten_state_detected(self):
        """Injury from prev chapter not mentioned in current should be flagged."""
        prev_tail = "他的左臂还在流血，伤口深可见骨。"
        text = "清晨。他站在院子里，望着远处的山。"
        report = run_hallucination_check(text, 5, prev_tail=prev_tail)
        forgotten = report.get("forgotten_state_items", [])
        assert len(forgotten) >= 1
