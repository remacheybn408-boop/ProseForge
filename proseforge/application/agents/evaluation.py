"""评估 harness（蓝图 V3-008 evaluation）。

- ``fixture_hash`` / ``evaluate_candidate``：既有契约（保留）。
- ``score_rubric``：7 维 rubric，每维 1–5 整数分，全部由**确定性检查**
  产出（分词/正则/统计，无模型调用）；模型分只作 advisory 记录，绝不入库。
  rubric 版本化：``RUBRIC_VERSION`` 随分数写入 payload。
"""

from __future__ import annotations

import hashlib
import json
import re
from statistics import mean, pstdev

RUBRIC_VERSION = "v3-rubric-1"
RUBRIC_DIMENSIONS: tuple[str, ...] = (
    "continuity",
    "character",
    "plot_causality",
    "style_adherence",
    "useful_review",
    "pacing",
    "cost_latency",
)

# 中文 AI 腔陈词列表（style_adherence 命中扣分，保持 ~10 条）
ANTI_AI_CLICHES: tuple[str, ...] = (
    "仿佛", "宛如", "不禁", "眼底闪过", "嘴角勾起",
    "深吸一口气", "心脏漏跳", "空气凝固", "时间静止", "不由自主",
)

# continuity 简易事实匹配器的否定/反义线索（subject 句内出现即记矛盾）
ANTONYMS: dict[str, str] = {"左": "右", "右": "左", "生": "死", "死": "生", "男": "女", "女": "男", "黑": "白", "白": "黑", "前": "后", "后": "前", "上": "下", "下": "上"}
TURN_MARKERS: tuple[str, ...] = ("突然", "但是", "然而", "没想到", "谁知")
CAUSAL_CONNECTIVES: tuple[str, ...] = ("因为", "由于", "所以", "于是", "因此", "为此")

# cost/latency 分档（比值相对 run A 基线；与发布规则的 40%/60% 阈值对齐）
_COST_STEPS: tuple[tuple[float, int], ...] = ((1.0, 5), (1.4, 4), (2.0, 3), (3.0, 2))
_LATENCY_STEPS: tuple[tuple[float, int], ...] = ((1.0, 5), (1.6, 4), (2.5, 3), (3.5, 2))
# pacing 句长变异系数（cv）分档见 score_rubric；章末钩子（？/…… 结尾）+1，封顶 5
_HOOK_ENDINGS: tuple[str, ...] = ("？", "……", "!", "?")


def fixture_hash(fixture: dict[str, object]) -> str: return hashlib.sha256(json.dumps(fixture, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def evaluate_candidate(candidate: dict[str, object], required: tuple[str, ...]) -> dict[str, object]:
    missing = [key for key in required if key not in candidate]
    return {"status": "UNSUPPORTED" if missing else "PASS", "missing": missing, "fixture_hash": fixture_hash(candidate)}


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。！？!?…]+", text) if part.strip()]


def find_fact_contradictions(text: str, facts: list[str]) -> list[dict[str, str]]:
    """简易事实匹配器：fact 形如 "subject:value"；subject 句内出现 value 的
    否定（不是/并非+value）或反义替换（ANTONYMS 单字替换后命中）即记一处矛盾。"""
    contradictions: list[dict[str, str]] = []
    for fact in facts:
        subject, separator, expected = fact.partition(":")
        if not separator or not subject.strip() or not expected.strip():
            continue
        subject, expected = subject.strip(), expected.strip()
        for sentence in _sentences(text):
            if subject not in sentence:
                continue
            negated = f"不是{expected}" in sentence or f"并非{expected}" in sentence
            antonym_hit = any(key in expected and expected.replace(key, opposite) in sentence for key, opposite in ANTONYMS.items())
            if negated or antonym_hit:
                contradictions.append({"fact": fact, "sentence": sentence})
    return contradictions


def count_unmotivated_turns(text: str) -> int:
    """转折标记（突然/但是/然而…）句内或前一句无因果连接词即记一次无动机转折。"""
    sentences = _sentences(text)
    unmotivated = 0
    for index, sentence in enumerate(sentences):
        if not any(marker in sentence for marker in TURN_MARKERS):
            continue
        window = sentence + (sentences[index - 1] if index > 0 else "")
        if not any(connective in window for connective in CAUSAL_CONNECTIVES):
            unmotivated += 1
    return unmotivated


def review_located_share(reviews: list[dict[str, object]]) -> float | None:
    """审校条目含证据 span（evidence 非空字符串/列表/含 span 的 dict）的比例。"""
    if not reviews:
        return None
    located = 0
    for review in reviews:
        evidence = review.get("evidence")
        if isinstance(evidence, str) and evidence.strip():
            located += 1
        elif isinstance(evidence, list) and evidence:
            located += 1
        elif isinstance(evidence, dict) and any(str(span).strip() for span in evidence.values()):
            located += 1
    return located / len(reviews)


def pacing_cv(text: str) -> float | None:
    sentences = _sentences(text)
    if len(sentences) < 2:
        return None
    lengths = [len(sentence) for sentence in sentences]
    center = mean(lengths)
    return pstdev(lengths) / center if center > 0 else None


def _band_score(ratio: float, steps: tuple[tuple[float, int], ...]) -> int:
    for ceiling, score in steps:
        if ratio <= ceiling:
            return score
    return 1


def score_rubric(
    text: str,
    *,
    facts: list[str] | tuple[str, ...] = (),
    banned_voice_words: list[str] | tuple[str, ...] = (),
    reviews: list[dict[str, object]] | tuple[dict[str, object], ...] = (),
    cost: dict[str, object] | None = None,
    advisory: dict[str, object] | None = None,
) -> dict[str, object]:
    """7 维确定性 rubric；返回 dimensions(1–5 int)、overall(1–5 int) 与证据计数。

    ``cost`` 键：budget_used / duration_ms / baseline_budget_used / baseline_duration_ms；
    基线缺失时 cost_latency 取中性 3 分（无法证明优于基线）。``advisory`` 只记录不使用。
    """
    contradictions = find_fact_contradictions(text, list(facts))
    continuity = 5 - min(4, len(contradictions))

    banned_hits = sum(text.count(word) for word in banned_voice_words if word)
    character = 5 - min(4, banned_hits)

    unmotivated = count_unmotivated_turns(text)
    plot_causality = 5 - min(4, unmotivated)

    cliche_hits = sum(text.count(cliche) for cliche in ANTI_AI_CLICHES)
    style_adherence = 5 - min(4, cliche_hits)

    share = review_located_share(list(reviews))
    useful_review = 1 if share is None else 1 + round(4 * share)

    cv = pacing_cv(text)
    if cv is None:
        pacing = 1
    else:
        pacing = 1 if cv < 0.15 else 2 if cv < 0.30 else 3 if cv < 0.50 else 4
        if text.rstrip().endswith(_HOOK_ENDINGS):
            pacing = min(5, pacing + 1)

    cost = dict(cost or {})
    base_budget, base_duration = float(cost.get("baseline_budget_used") or 0), float(cost.get("baseline_duration_ms") or 0)
    cost_ratio = latency_ratio = None
    if base_budget > 0 and base_duration > 0:
        cost_ratio = float(cost.get("budget_used") or 0) / base_budget
        latency_ratio = float(cost.get("duration_ms") or 0) / base_duration
        cost_latency = min(_band_score(cost_ratio, _COST_STEPS), _band_score(latency_ratio, _LATENCY_STEPS))
    else:
        cost_latency = 3  # 无基线：中性分，发布判定由 A/B 比值兜底

    dimensions = {
        "continuity": continuity,
        "character": character,
        "plot_causality": plot_causality,
        "style_adherence": style_adherence,
        "useful_review": useful_review,
        "pacing": pacing,
        "cost_latency": cost_latency,
    }
    return {
        "rubric_version": RUBRIC_VERSION,
        "dimensions": dimensions,
        "overall": round(mean(dimensions.values())),
        "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "evidence": {
            "contradictions": len(contradictions),
            "banned_voice_hits": banned_hits,
            "unmotivated_turns": unmotivated,
            "cliche_hits": cliche_hits,
            "review_located_share": share,
            "pacing_cv": cv,
            "cost_ratio": cost_ratio,
            "latency_ratio": latency_ratio,
        },
        "advisory": dict(advisory or {}),  # 模型分：仅供参考，绝不参与入库分数
    }
