"""确定性 rubric（application/agents/evaluation.score_rubric）与 fixture 可复现性测试。

fixtures.json 记录每个合成片段的 sha256 与各维期望区间：哈希不复现即失败
（片段被改动），分数落在区间外即失败（rubric 行为漂移）。
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from proseforge.application.agents.evaluation import (
    ANTI_AI_CLICHES,
    RUBRIC_DIMENSIONS,
    RUBRIC_VERSION,
    count_unmotivated_turns,
    find_fact_contradictions,
    review_located_share,
    score_rubric,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_cases() -> list[dict[str, object]]:
    manifest = json.loads((FIXTURES_DIR / "fixtures.json").read_text(encoding="utf-8"))
    assert manifest["rubric_version"] == RUBRIC_VERSION
    return list(manifest["cases"])


def test_fixture_hashes_reproduce():
    cases = _load_cases()
    assert len(cases) == 3
    for case in cases:
        data = (FIXTURES_DIR / str(case["file"])).read_bytes()
        assert hashlib.sha256(data).hexdigest() == case["sha256"], f"fixture drifted: {case['id']}"


def test_rubric_scores_within_expected_bounds():
    for case in _load_cases():
        text = (FIXTURES_DIR / str(case["file"])).read_text(encoding="utf-8")
        result = score_rubric(
            text,
            facts=case["facts"],
            banned_voice_words=case["banned_voice_words"],
            reviews=case["reviews"],
            cost=case["cost"],
        )
        assert result["rubric_version"] == RUBRIC_VERSION
        assert set(result["dimensions"]) == set(RUBRIC_DIMENSIONS)
        for dimension, (low, high) in case["expected"].items():
            score = result["dimensions"][dimension]
            assert isinstance(score, int) and 1 <= score <= 5
            assert low <= score <= high, f"{case['id']}.{dimension}: {score} not in [{low}, {high}]"
        assert result["overall"] == round(sum(result["dimensions"].values()) / len(RUBRIC_DIMENSIONS))
        # 复算一次：确定性 rubric 同输入同分数
        again = score_rubric(text, facts=case["facts"], banned_voice_words=case["banned_voice_words"], reviews=case["reviews"], cost=case["cost"])
        assert again["dimensions"] == result["dimensions"]


def test_model_scores_are_advisory_only():
    text = "短句。长句用来铺开一段相对完整的描写，让节奏出现起伏。"
    plain = score_rubric(text)
    advised = score_rubric(text, advisory={"continuity": 1, "note": "model disagrees"})
    assert advised["dimensions"] == plain["dimensions"]  # 模型分绝不参与入库分数
    assert advised["advisory"] == {"continuity": 1, "note": "model disagrees"}
    assert plain["advisory"] == {}


def test_fact_matcher_finds_only_real_contradictions():
    facts = ["林雪:左撇子", "顾岩:沉默寡言"]
    assert find_fact_contradictions("林雪用左手开门。顾岩话很少。", facts) == []
    hits = find_fact_contradictions("林雪是个右撇子。林雪并非左撇子。顾岩保持沉默。", facts)
    assert len(hits) == 2
    assert {hit["fact"] for hit in hits} == {"林雪:左撇子"}


def test_unmotivated_turns_need_causal_support():
    assert count_unmotivated_turns("因为下雨，他留了下来。然而雨没有停。") == 0  # 前句有因果
    assert count_unmotivated_turns("他走进教室。突然，灯灭了。") == 1


def test_review_share_and_cliche_and_cost_bands():
    assert review_located_share([]) is None
    assert review_located_share([{"finding": "a", "evidence": "第三段"}, {"finding": "b"}]) == 0.5

    cliche_text = "。".join(ANTI_AI_CLICHES[:4])  # 4 处命中：style_adherence 触底 1
    result = score_rubric(cliche_text)
    assert result["dimensions"]["style_adherence"] == 1
    assert result["evidence"]["cliche_hits"] == 4

    no_baseline = score_rubric("短。长得多得多的句子。")
    assert no_baseline["dimensions"]["cost_latency"] == 3  # 无基线取中性分
    over_budget = score_rubric("短。长得多得多的句子。", cost={"budget_used": 5000, "duration_ms": 9000, "baseline_budget_used": 1000, "baseline_duration_ms": 10000})
    assert over_budget["dimensions"]["cost_latency"] == 1  # cost ratio 5.0 超最高档


def test_pacing_hook_bonus():
    flat = "他走进教室坐了下来。他打开课本翻到第十页。他拿起笔开始抄写板书。"
    hooked = flat + "可是他桌上的纸条，是谁留下的？"
    assert score_rubric(hooked)["dimensions"]["pacing"] > score_rubric(flat)["dimensions"]["pacing"]
