"""
test_guard_observability.py — CODE_REVIEW #7 + #6 回归

#7: guard 崩溃（fail-open 降级 WARN）应在 GuardSummary.crashed_guards 显式记账，
    并能 save/load 往返。
#6: L2 聚合 guard 的子检测身份（source_guard）应一路保留到去重，使
    "≥2 个来源共同发现" 的合并规则真正生效（非"恒为 1"）。
"""
from src.utils.guard_result import GuardSummary, GuardResult
from src.guards.guard_registry import _adapt_legacy_dict
from src.pipeline.report_deduplicator import deduplicate_warnings


def test_crashed_guards_collected_in_summary():
    s = GuardSummary(chapter_no=1)
    s.add_result(GuardResult(guard="ok_guard", status="PASS"))
    s.add_result(GuardResult(guard="boom_guard", status="WARN", error="kaboom"))
    assert s.crashed_guards == ["boom_guard"]
    # 干净的 guard 不进 crashed
    assert "ok_guard" not in s.crashed_guards


def test_crashed_guards_survive_save_load(tmp_path):
    s = GuardSummary(chapter_no=3)
    s.add_result(GuardResult(guard="boom", status="WARN", error="x"))
    p = tmp_path / "summary.json"
    s.save(str(p))
    loaded = GuardSummary.load(str(p))
    assert loaded.crashed_guards == ["boom"]
    assert "crashed_guards" in p.read_text(encoding="utf-8")


def test_dedup_counts_distinct_subcheck_sources():
    """#6 回归：同一 L2 聚合 guard 下两个子检测，去重应识别为 2 个来源并合并。"""
    raw = {
        "status": "WARNING",
        "flags": [
            {"message": "抽象总结过多", "code": "ABSTRACT_OVERUSE",
             "source": "anti_ai_guard", "confidence": 0.6},
            {"message": "缺具体锚点", "code": "ANCHOR_MISSING",
             "source": "concrete_anchor_guard", "confidence": 0.6},
        ],
    }
    res = _adapt_legacy_dict("prose_authenticity_guard", raw)
    # 子检测身份保留在 source_guard
    assert {f.source_guard for f in res.findings} == {"anti_ai_guard", "concrete_anchor_guard"}

    s = GuardSummary(chapter_no=1)
    s.add_result(res)
    merged = deduplicate_warnings(s.get_warnings(), min_confidence=0.0)
    assert len(merged) == 1
    assert set(merged[0]["reported_by"]) == {"anti_ai_guard", "concrete_anchor_guard"}
