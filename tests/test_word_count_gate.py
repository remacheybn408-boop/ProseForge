"""
test_word_count_gate.py — 字数门禁 V5 测试
"""
import pytest
from copy import deepcopy

import src.pipeline.post as post_m
from src.pipeline._base import _count_chinese, App, DEFAULT_CONFIG


@pytest.fixture
def app():
    cfg = deepcopy(DEFAULT_CONFIG)
    cfg["db_path"] = ":memory:"
    return App(cfg, "test_novel", "测试小说", 1)


class TestChineseCount:
    def test_pure_chinese(self):
        assert _count_chinese("这是一段测试文本") == 8
    def test_mixed(self):
        assert _count_chinese("ABC这是一段test文本123") == 6
    def test_punctuation(self):
        assert _count_chinese("你好，世界！") == 6


class TestWordCountGateV5:
    def test_normal_below_min_fails(self, app):
        """Normal chapters below config.example min fail."""
        post_m.app = app
        content = "测试" * 600  # 1200
        result, wc, eff_min = post_m.word_count_gate(content, 1, "normal")
        assert not result

    def test_normal_authorized_short_passes_when_allowed(self, app):
        """allow_short_chapter lets normal chapters pass inside authorized_short range."""
        post_m.app = app
        content = "字" * 400
        result, wc, eff_min = post_m.word_count_gate(content, 1, "normal")
        assert result == "authorized_short"
        assert wc == 400

    def test_normal_too_short_still_fails_when_short_allowed(self, app):
        """Short-chapter permission still enforces authorized_short.min."""
        post_m.app = app
        content = "字" * 299
        result, wc, eff_min = post_m.word_count_gate(content, 1, "normal")
        assert not result

    def test_normal_short_above_authorized_max_fails(self, app):
        """Short-chapter permission does not pass chapters above authorized_short.max."""
        post_m.app = app
        content = "字" * 1100
        result, wc, eff_min = post_m.word_count_gate(content, 1, "normal")
        assert not result

    def test_normal_short_fails_when_not_allowed(self, app):
        """400-char normal chapters fail when allow_short_chapter is disabled."""
        app.allow_short_chapter = False
        post_m.app = app
        content = "字" * 400
        result, wc, eff_min = post_m.word_count_gate(content, 1, "normal")
        assert not result

    def test_normal_1900_passes(self, app):
        """Normal 1900 passes (best range)"""
        post_m.app = app
        content = "测试" * 950  # 1900
        result, wc, eff_min = post_m.word_count_gate(content, 1, "normal")
        assert result == "ideal"

    def test_normal_2400_ideal(self, app):
        post_m.app = app
        content = "测试" * 1200  # 2400
        result, wc, eff_min = post_m.word_count_gate(content, 1, "normal")
        assert result == "ideal"

    def test_normal_3500_warns(self, app):
        """Normal > 3300 oversize"""
        post_m.app = app
        content = "测试" * 1750  # 3500
        result, wc, eff_min = post_m.word_count_gate(content, 1, "normal")
        assert result == "oversize"

    def test_key_2000_passes(self, app):
        """Key chapter 2000 is now inside the config.example ideal range."""
        post_m.app = app
        content = "测试" * 1000  # 2000
        result, wc, eff_min = post_m.word_count_gate(content, 1, "key")
        assert result == "ideal"

    def test_climax_2300_passes(self, app):
        """Climax 2300 passes (not forced to 4200)"""
        post_m.app = app
        content = "测试" * 1150  # 2300
        result, wc, eff_min = post_m.word_count_gate(content, 1, "climax")
        assert result == "ideal"

    def test_climax_6000_oversize(self, app):
        """Climax > 5500 fails"""
        post_m.app = app
        content = "测试" * 3000  # 6000
        result, wc, eff_min = post_m.word_count_gate(content, 1, "climax")
        assert result == "oversize"
