"""
test_scene_delta_guard.py — 场景推进证据门禁测试
"""
import pytest, json, sys, os
from src.guards.scene_delta_guard import run_scene_delta_check


class TestSceneDeltaPass:
    def test_multi_scene_content_passes(self):
        """多场景内容应该通过"""
        content = (
            "清晨。他站起，走出房门。矿道方向传来敲击声。\n\n"
            "\"发现什么了？\"他走过去问。\n"
            "老铁头也不回：\"灵石脉的走向不对劲，这边偏了三度。\"\n\n"
            "傍晚。他蹲在矿道拐角，用刀尖刮下石壁上的粉末。\n"
            "粉末在掌心微微发光——这是灵频偏移的迹象。"
        )
        report = run_scene_delta_check(content)
        assert report["effective_scene_delta_count"] >= 1

    def test_conflict_scene_delta(self):
        """有冲突的场景推进力更强"""
        content = (
            "\"你不能进去！\"守卫拦住了他。\n"
            "他握紧拳头，但没有动手。\"让开。\"\n"
            "守卫拔出刀。\"再往前一步，我就不客气了。\"\n\n"
            "冲突之中他发现了守卫眼里的恐惧。\n"
            "那不是忠心——是被威胁。\n"
            "\"有人在逼你？\"他问。\n"
            "守卫的刀尖抖了一下。"
        )
        report = run_scene_delta_check(content)
        # Conflict + plot + character_state = decent delta
        assert report["effective_scene_delta_count"] >= 2


class TestSceneDeltaFail:
    def test_monologue_only_low_delta(self):
        """纯内心独白推进力低"""
        content = (
            "他知道这一切都不容易。他明白自己还有很多要学。\n"
            "他想起师父说过的话。他觉得自己可能永远也追不上。\n"
            "但他又觉得自己不应该放弃。他想着想着，天就黑了。"
        )
        report = run_scene_delta_check(content)
        # Pure monologue should have low effective delta
        assert report["effective_scene_delta_count"] < 3

    def test_short_content_low_delta(self):
        """过短内容推进力不足"""
        content = "天亮了。\n天黑了。\n又是一天。"
        report = run_scene_delta_check(content)
        assert report["effective_scene_delta_count"] < 3
