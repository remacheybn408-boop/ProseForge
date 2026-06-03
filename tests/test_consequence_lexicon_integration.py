"""test_consequence_lexicon_integration.py — 确保叙事化代价被正确识别"""

TEXT = """他从水里爬出来，胸口一阵肺痉挛，喉咙里全是铁锈味。
咳出来的水沫子挂在下巴上，右手还在抖。
"""


def test_consequence_lexicon_counts_narrative_costs():
    """consequence_lexicon must recognize 肺痉挛/铁锈味/水沫子/手抖 as physical costs."""
    from consequence_lexicon import has_minimum_visible_cost
    passed, count, details = has_minimum_visible_cost(TEXT, min_cost=2)
    assert passed, f"Expected min 2 visible costs, got {count}"
    assert count >= 2
    assert details["physical_count"] >= 4, (
        f"Expected >=4 physical costs (肺痉挛/铁锈味/水沫子/手抖), "
        f"got {details['physical_count']}"
    )


def test_scene_causality_accepts_narrative_costs():
    """scene_causality must not report '整章未检测到任何可见后果' for narrative costs."""
    from src.guards.scene_causality_guard import run_scene_causality_check
    report = run_scene_causality_check(TEXT, chapter_no=1)
    text_report = str(report)
    assert "整章未检测到任何可见后果" not in text_report
    assert "代价缺失" not in text_report


def test_concrete_anchor_accepts_narrative_costs():
    """concrete_anchor must not report '整章未检测到任何可见后果' for narrative costs."""
    from src.guards.concrete_anchor_guard import run_concrete_anchor_check
    report = run_concrete_anchor_check(TEXT, chapter_no=1)
    text_report = str(report)
    assert "整章未检测到任何可见后果" not in text_report
