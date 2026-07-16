"""
test_continuity_evidence_guard.py — 章章连续证据门禁测试
"""
from src.guards.continuity_evidence_guard import run_continuity_evidence_check


class TestContinuityEvidencePass:
    def test_first_chapter_auto_pass(self):
        """第一章自动通过"""
        content = "清晨。他站在院子里，望着远处的山。\n这是平凡的一天。"
        report = run_continuity_evidence_check(1, content)
        assert report["final_decision"] == "PASS"
        assert report["previous_tail_used"] is None

    def test_clean_continuity_passes(self):
        """明确承接上一章应该通过"""
        prev_tail = "他握住那块灵石，感觉掌心传来的微热。矿道深处还有未探明的区域。"
        content = "第二天一早，他攥着灵石走进矿道深处。掌心的余温还在。"
        report = run_continuity_evidence_check(2, content, prev_tail=prev_tail)
        assert report["previous_tail_used"] is True
        # Should have some continuity
        assert report["continuity_evidence_score"] >= 0.5

    def test_injury_carried_forward(self):
        """上一章伤势被继承应该通过"""
        prev_tail = "他的左臂还在流血，伤口深可见骨。"
        content = "清晨。左臂的伤口还在隐隐作痛，他咬牙站起。"
        report = run_continuity_evidence_check(2, content, prev_tail=prev_tail)
        assert report["previous_tail_used"] is True


class TestContinuityEvidenceFail:
    def test_missing_tail_used(self):
        """v0.7.1: 无上章数据时 PASS 而非 FAIL（新小说/新卷前几章正常现象）"""
        content = "这是一段全新的文字，与上一章毫无关系。"
        report = run_continuity_evidence_check(5, content, prev_tail="")
        assert report["previous_tail_used"] is False
        assert report["final_decision"] == "PASS"

    def test_discovery_hooks_missing(self):
        """上一章的重要发现未被承接"""
        prev_tail = "他发现了灵石矿脉深处的一个巨大空洞。这可能是整个矿区的关键秘密。"
        content = "早上好。他起床喝了杯茶。今天天气不错。"
        report = run_continuity_evidence_check(3, content, prev_tail=prev_tail)
        assert report["previous_tail_used"] is True
        # Should have missing hooks since discovery not acknowledged
        assert len(report["hard_missing_hooks"]) > 0

    def test_location_discontinuity(self):
        """被困状态下地点跳转"""
        prev_tail = "他被困在矿道最深处，无法离开。身后传来坍塌的声音。"
        content = "他出现在繁华的坊市中央，周围人来人往，叫卖声不绝。"
        report = run_continuity_evidence_check(4, content, prev_tail=prev_tail)
        assert len(report["continuity_conflicts"]) > 0
