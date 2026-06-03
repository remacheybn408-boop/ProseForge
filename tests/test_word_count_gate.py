"""
test_word_count_gate.py — 字数门禁 V5 测试
"""
import pytest, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from chapter_pipeline import _count_chinese, App, DEFAULT_CONFIG


@pytest.fixture
def app():
    cfg = DEFAULT_CONFIG.copy()
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
        """Normal < 1900 fails"""
        import chapter_pipeline as cp; cp.app = app
        content = "测试" * 900  # 1800
        result, wc = cp.word_count_gate(content, 1, "normal")
        assert result == False

    def test_normal_1900_passes(self, app):
        """Normal 1900 passes (best range)"""
        import chapter_pipeline as cp; cp.app = app
        content = "测试" * 950  # 1900
        result, wc = cp.word_count_gate(content, 1, "normal")
        assert result == "ideal"

    def test_normal_2400_ideal(self, app):
        import chapter_pipeline as cp; cp.app = app
        content = "测试" * 1200  # 2400
        result, wc = cp.word_count_gate(content, 1, "normal")
        assert result == "ideal"

    def test_normal_3500_warns(self, app):
        """Normal > 3300 oversize"""
        import chapter_pipeline as cp; cp.app = app
        content = "测试" * 1750  # 3500
        result, wc = cp.word_count_gate(content, 1, "normal")
        assert result == "oversize"

    def test_key_2000_passes(self, app):
        """Key chapter 2000 passes (not forced to 3300)"""
        import chapter_pipeline as cp; cp.app = app
        content = "测试" * 1000  # 2000
        result, wc = cp.word_count_gate(content, 1, "key")
        assert result == True  # passes, below best_min but above min

    def test_climax_2300_passes(self, app):
        """Climax 2300 passes (not forced to 4200)"""
        import chapter_pipeline as cp; cp.app = app
        content = "测试" * 1150  # 2300
        result, wc = cp.word_count_gate(content, 1, "climax")
        assert result == "ideal"

    def test_climax_6000_oversize(self, app):
        """Climax > 5500 fails"""
        import chapter_pipeline as cp; cp.app = app
        content = "测试" * 3000  # 6000
        result, wc = cp.word_count_gate(content, 1, "climax")
        assert result == "oversize"
