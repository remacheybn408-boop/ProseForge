"""
test_padding_guard.py — 防水文证据门禁测试
"""
import pytest, json, sys, os
from src.guards.padding_guard import run_padding_check


class TestPaddingPass:
    def test_clean_content_passes(self):
        """干净内容应该通过"""
        content = "清晨。他站起，走到院子里。\n拿起斧头，劈了三根柴。\n\"今天要下雨。\"老张说。\n他点点头，继续劈。"
        report = run_padding_check(content)
        assert report["padding_score"] <= 20
        assert report["padding_level"] in ("none", "warning")

    def test_action_heavy_content_passes(self):
        """动作密集的内容应该通过"""
        content = ("他推开门走进房间。拿起桌上的杯子喝了一口。\n"
                   "\"你来了。\"她说。\n\"嗯。\"他放下杯子。\n"
                   "窗外传来雨声。他走到窗边拉上窗帘。")
        report = run_padding_check(content)
        assert report["padding_detected"] is False


class TestPaddingFail:
    def test_repeated_explanation_raises_score(self):
        """反复解释同一设定会提高分数"""
        content = ("灵气是这个世界的基础能量。灵气可以用来修炼。\n"
                   "也就是说，灵气就是修士吸收的能量。\n"
                   "换言之，没有灵气就无法修炼。\n"
                   "说白了，灵气决定了一个人的修炼上限。\n"
                   "简单来说，灵气的浓度影响修炼速度。\n"
                   "这意味着灵气是关键。\n"
                   "所以说灵气很重要。\n"
                   "总之，灵气就是一切。")
        report = run_padding_check(content)
        assert report["repeated_explanation_count"] > 0

    def test_tail_padding_detected(self):
        """末尾总结算水文"""
        content = ("他完成了任务。\n" * 50 +
                   "总之，他知道这一切都值得了。他终于做到了。"
                   "一切都会好起来的。这就是他所追求的。")
        report = run_padding_check(content)
        # May detect tail padding
        assert report["tail_padding_detected"] is True

    def test_empty_monologue_raises_score(self):
        """空转心理提高分数"""
        content = ("他知道这很难。他明白自己不够强。\n"
                   "他意识到前方还有很长的路。\n"
                   "他觉得疲惫。他感觉无力。\n"
                   "他想起过去的失败。他知道自己必须坚持。")
        report = run_padding_check(content)
        # Empty monologue without actions should be detected
        assert report["empty_inner_monologue_count"] > 0
