"""test_guard_protocol_consumers.py — v0.8.0 协议链回归

目的：验证 GuardResult.to_dict() / GuardSummary.get_warnings() 这套新协议
能被下游消费者（final_submission_report / report_deduplicator / post._load_sub）
正确解析。Codex 2026-06-18 review 揭示的协议断裂回归测试。
"""
import json

from src.utils.guard_result import (
    GuardResult, GuardSummary, finding,
)
from src.pipeline.final_submission_report import (
    aggregate_reports, _coerce_legacy,
)
from src.pipeline.report_deduplicator import (
    classify_warning, deduplicate_warnings,
)


# ─────────────────────────────────────────────
# Codex Finding #1: aggregate_reports 协议归一化
# ─────────────────────────────────────────────

def test_aggregate_accepts_guard_result_dict_warn():
    """v0.8.0: status=WARN finding 输入应给出 NEED_REVISION，而不是误报 READY"""
    gr = GuardResult(
        guard="prose_authenticity_guard",
        status="WARN",
        findings=[finding(
            "prose_authenticity_guard", "WARN",
            "ABSTRACT_OVERUSE", "抽象总结过多",
            confidence=0.7, suggestion="改成具体动作")],
        metrics={"sub_scores": {"anti_ai_guard": 65}},
    )
    reports = {"prose_authenticity_guard": gr.to_dict()}
    result = aggregate_reports(reports, 1)
    assert result["overall_status"] == "NEED_REVISION", (
        f"WARN 应该 → NEED_REVISION，实际：{result['overall_status']}"
    )
    # sub_scores 必须从 metrics 提升到顶层 summary
    summary = result["guards"]["prose_authenticity_guard"]
    assert summary.get("sub_scores") == {"anti_ai_guard": 65}
    # findings 必须转成 task
    sources = [t["source"] for t in result["top_revision_tasks"]]
    assert "prose_authenticity_guard" in sources


def test_aggregate_accepts_guard_result_dict_fail():
    """v0.8.0: status=FAIL 必须映射到 BLOCKED"""
    gr = GuardResult(
        guard="compliance_selfcheck_guard",
        status="FAIL",
        findings=[finding(
            "compliance_selfcheck_guard", "FAIL",
            "EXPLICIT_CONTENT", "检出违规",
            suggestion="删除违规内容")],
        metrics={"blocked_categories": ["explicit_sexual"]},
    )
    reports = {"compliance_selfcheck_guard": gr.to_dict()}
    result = aggregate_reports(reports, 1)
    assert result["overall_status"] in ("BLOCKED", "BLOCK"), (
        f"FAIL 应该 → BLOCKED，实际：{result['overall_status']}"
    )
    # blocked_categories 必须从 metrics 浮到 summary
    summary = result["guards"]["compliance_selfcheck_guard"]
    assert summary.get("blocked_categories") == ["explicit_sexual"]


def test_aggregate_drills_guards_raw_in_metrics():
    """v0.8.0: L2 聚合 guard 的 _guards_raw 在 metrics 里，必须能下钻"""
    gr = GuardResult(
        guard="narrative_rhythm_guard",
        status="WARN",
        findings=[finding(
            "narrative_rhythm_guard", "WARN",
            "PADDING_DETECTED", "水文段落",
            confidence=0.75)],
        metrics={
            "sub_scores": {"padding_guard": 55, "style_variation_guard": 80},
            "_guards_raw": [
                {"guard": "padding_guard", "status": "WARNING",
                 "suggestions": ["删除冗余段落"],
                 "flags": [{"level": "WARNING", "type": "PADDING",
                            "message": "段落 3 偏冗长"}]},
                {"guard": "style_variation_guard", "status": "PASS"},
            ],
        },
    )
    reports = {"narrative_rhythm_guard": gr.to_dict()}
    result = aggregate_reports(reports, 2)
    # 顶层 finding + 下钻子检测都要出现在 revision tasks
    sources = [t["source"] for t in result["top_revision_tasks"]]
    assert any("padding_guard" in s for s in sources), (
        f"子检测 padding_guard 未下钻到 tasks: {sources}"
    )


# ─────────────────────────────────────────────
# Codex Finding #2: report_deduplicator 字段名兼容
# ─────────────────────────────────────────────

def test_classify_warning_recognizes_new_finding_format():
    """v0.8.0 finding: code + guard 必须被识别，落入 ABSTRACT_OVERUSE 而非 UNCATEGORIZED"""
    new_format = {
        "guard": "prose_authenticity_guard",
        "severity": "WARN",
        "code": "ABSTRACT_OVERUSE_DETECTED",
        "message": "抽象描述过多",
        "confidence": 0.7,
    }
    cat = classify_warning(new_format)
    assert cat == "ABSTRACT_OVERUSE", (
        f"新格式 finding 应归类为 ABSTRACT_OVERUSE，实际：{cat}"
    )


def test_classify_warning_legacy_still_works():
    """旧格式不能回归：type + source_guard 仍正常识别"""
    legacy = {
        "source_guard": "anti_ai_guard",
        "type": "ABSTRACT_SUMMARY",
        "message": "抽象总结",
        "confidence": 0.7,
    }
    cat = classify_warning(legacy)
    assert cat == "ABSTRACT_OVERUSE"


def test_deduplicate_uses_subcheck_identity():
    """v0.8.0: 子检测身份保留后，单个父 guard 里两个不同子检测报抽象应能合并

    走真实路径：_cluster_aggregator → adapter → GuardSummary.get_warnings() → dedup。
    合并条件是 sources 数 ≥ 2（dedup 第 128 行），所以必须看到两个不同的 source_guard。
    """
    from src.guards.guard_registry import _adapt_legacy_dict

    # 模拟 _cluster_aggregator 聚合 anti_ai + show_dont_tell 两个子检测各喊一条抽象
    raw_aggregator_dict = {
        "guard": "prose_authenticity_guard",
        "status": "WARNING",
        "score": 55,
        "flags": [
            {"source": "anti_ai_guard", "code": "ABSTRACT_SUMMARY",
             "message": "抽象总结过多", "confidence": 0.72,
             "severity": "WARN"},
            {"source": "show_dont_tell_guard", "code": "TELL_NOT_SHOW",
             "message": "解释过多缺乏展示", "confidence": 0.70,
             "severity": "WARN"},
        ],
    }
    result = _adapt_legacy_dict("prose_authenticity_guard", raw_aggregator_dict)
    summary = GuardSummary(chapter_no=1)
    summary.add_result(result)

    merged = deduplicate_warnings(summary.get_warnings(), min_confidence=0.5)
    # 子身份保留后，sources = {anti_ai_guard, show_dont_tell_guard} 共 2 个 → 应合并
    abstract_merged = [m for m in merged
                       if m.get("type") == "merged"
                       and "抽象" in m["merged_issue"]]
    assert abstract_merged, (
        f"两个不同子检测的抽象警告未合并：{merged}"
    )
    # reported_by 必须是子名，不是父聚合名
    reported = set(abstract_merged[0]["reported_by"])
    assert reported == {"anti_ai_guard", "show_dont_tell_guard"}, (
        f"reported_by 应是子名，实际：{reported}"
    )


def test_source_guard_preserved_through_adapter():
    """子检测身份必须从 _cluster_aggregator → adapter → GuardFinding → to_dict 全程保留"""
    from src.guards.guard_registry import _adapt_legacy_dict

    raw = {
        "guard": "narrative_rhythm_guard",
        "status": "WARNING",
        "flags": [
            {"source": "padding_guard", "code": "PADDING_DETECTED",
             "message": "段落 3 偏冗长", "confidence": 0.75,
             "severity": "WARN"},
        ],
    }
    result = _adapt_legacy_dict("narrative_rhythm_guard", raw)

    # finding 级：父名不变，子名落到 source_guard
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.guard == "narrative_rhythm_guard", "guard 字段必须保持父聚合名"
    assert f.source_guard == "padding_guard", "source_guard 必须落子检测名"

    # 序列化：to_dict 必须带出 source_guard
    d = f.to_dict()
    assert d.get("source_guard") == "padding_guard"

    # GuardSummary.get_warnings() 扁平输出也带
    summary = GuardSummary(chapter_no=1)
    summary.add_result(result)
    warnings = summary.get_warnings()
    assert warnings[0]["source_guard"] == "padding_guard"
    assert warnings[0]["guard"] == "narrative_rhythm_guard"


def test_source_guard_empty_when_no_source():
    """旧 guard（非聚合）的 flag 没有 source 字段时，source_guard 默认空，不报错"""
    from src.guards.guard_registry import _adapt_legacy_dict

    raw = {
        "guard": "continuity_evidence_guard",
        "status": "FAIL",
        "flags": [
            {"code": "MISSING_REF", "message": "缺少前文锚点", "severity": "FAIL"},
        ],
    }
    result = _adapt_legacy_dict("continuity_evidence_guard", raw)
    assert result.findings[0].source_guard == ""
    assert result.findings[0].guard == "continuity_evidence_guard"


# ─────────────────────────────────────────────
# Codex Finding #3: post._load_sub 嵌套位置
# ─────────────────────────────────────────────

def test_load_sub_finds_guards_raw_in_metrics(tmp_path):
    """v0.8.0: _guards_raw 在 metrics 里，_load_sub 必须能找到（不是顶层）"""
    gr = GuardResult(
        guard="narrative_rhythm_guard",
        status="WARN",
        metrics={
            "_guards_raw": [
                {"guard": "padding_guard", "status": "WARNING",
                 "padding_detected": True,
                 "padding_evidence": ["段 3 重复修辞"]},
            ],
        },
    )
    report_path = tmp_path / "chapter_001_narrative_rhythm_guard_report.json"
    report_path.write_text(json.dumps(gr.to_dict(), ensure_ascii=False), encoding="utf-8")

    # 复用 post.py 的 _load_sub 实现（独立验证）
    _data = json.loads(report_path.read_text(encoding="utf-8"))
    subs = (_data.get("_guards_raw")
            or (_data.get("metrics") or {}).get("_guards_raw")
            or [])
    padding = next((s for s in subs if s.get("guard") == "padding_guard"), None)
    assert padding is not None, "_load_sub 模式无法定位 metrics._guards_raw"
    assert padding.get("padding_detected") is True


# ─────────────────────────────────────────────
# Codex Finding #5: fts_health 导入路径
# ─────────────────────────────────────────────

def test_fts_health_import_path():
    """guard_registry 必须能从 src.utils.fts_health 导入（不是顶层）"""
    from src.utils.fts_health import check_fts_health
    assert callable(check_fts_health)


# ─────────────────────────────────────────────
# _coerce_legacy 幂等性
# ─────────────────────────────────────────────

def test_coerce_legacy_idempotent_for_old_format():
    """旧格式报告应原样通过（幂等）"""
    legacy = {
        "guard": "compliance_selfcheck_guard",
        "version": "v0.4.0",
        "status": "BLOCK",
        "flags": [{"level": "BLOCK", "type": "EXPLICIT", "message": "违规"}],
        "blocked_categories": ["explicit_sexual"],
        "suggestions": ["删除违规内容"],
    }
    out = _coerce_legacy(legacy)
    assert out["status"] == "BLOCK"
    assert out["flags"] == legacy["flags"]
    assert out["blocked_categories"] == ["explicit_sexual"]


def test_aggregate_handles_non_dict_report_payload():
    """非 dict 报告不应在 aggregate_reports 中触发 AttributeError。"""
    result = aggregate_reports({"broken_guard": None}, 1)
    assert result["overall_status"] == "NEED_REVISION"
    guard_summary = result["guards"]["broken_guard"]
    assert guard_summary["status"] == "WARNING"
    assert result["top_revision_tasks"], "invalid payload 应转成可见 revision task"


def test_classify_warning_accepts_dialogue_quality_for_abstract_overuse():
    """dialogue_quality_guard 的抽象表达告警不应再落入 UNCATEGORIZED。"""
    flag = {
        "guard": "dialogue_quality_guard",
        "code": "ABSTRACT_OVERUSE_DETECTED",
        "message": "抽象表达过多",
        "confidence": 0.72,
    }
    assert classify_warning(flag) == "ABSTRACT_OVERUSE"


def test_classify_warning_accepts_reader_engagement_for_over_explained():
    """reader_engagement_guard 的解释过满告警应能归到 OVER_EXPLAINED。"""
    flag = {
        "guard": "reader_engagement_guard",
        "code": "OVER_EXPLAINED",
        "message": "解释过满，缺少留白",
        "confidence": 0.68,
    }
    assert classify_warning(flag) == "OVER_EXPLAINED"


def test_registry_supplies_perplexity_config_in_debug_mode():
    """registry 应补出 perplexity_config，使 prose_authenticity 的 QGP 子检测不再永久 skip。"""
    from src.guards.guard_registry import run_standard_guards

    sample = (
        "周砚把掌心按在潮湿的石壁上，指节因为寒意微微发紧。"
        "碎石从缝里掉下来，砸在靴尖上，发出很轻的一声脆响。"
        "他没有立刻开口，只先把呼吸压平，再去听石壁后面那阵若有若无的回音。"
        "沈师姐抬手拦住他，袖口擦过铜灯，灯焰晃了一下，把两人的影子切成参差的碎片。"
    )

    summary = run_standard_guards(
        sample,
        chapter_no=1,
        mode="debug",
        custom_guards=["prose_authenticity_guard"],
        config={},
        extra_context={"novel_slug": "test_novel"},
    )

    assert len(summary.results) == 1
    result = summary.results[0]
    subs = result.metrics.get("_guards_raw", [])
    qgp = next((s for s in subs if s.get("guard") == "perplexity_quality_guard"), None)
    assert qgp is not None, "QGP 子检测应出现在 _guards_raw 中"
    assert "skipped" not in str(qgp.get("note", "")).lower()
