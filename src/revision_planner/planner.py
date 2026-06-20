"""planner.py — MVP 规划器：list[Finding] → list[Action]。

当前作用域（MVP）：
- 只处理 anti_ai 的**固定短语**类 codes（CHEN_MO_JI_MIAO 等）
- 不处理变量模式类（NA_YI_KE / XIN_ZHONG_YONG_QI 等需要 sub-pattern 解析）
- 不处理聚合类 codes（AI_CLICHE_OVERFLOW 等是元信号，不可执行）

冲突解决（MVP）：
- 同一 char_span 多个 finding → 取第一个产生 action，其余跳过
- 后续可扩展：按 severity 排序、按 detector 来源加权

确定性：用 (chapter content hash + finding code) 派生 seed，避免每次跑结果不同。
"""
from __future__ import annotations
import hashlib
import random
from typing import Iterable

from .action import Action, OP_REPLACE, OP_DELETE
from .schema import Finding


# code → 替换候选列表
# 设计原则：保留意思，去模板化，不引入引号 / 破折号
PHRASE_REPLACEMENTS: dict[str, list[str]] = {
    # 完整定型短语（regex 是字面）
    "CHEN_MO_JI_MIAO": ["顿了顿", "沉默了一下", "停了片刻"],
    "SHEN_XI_YI_KOU_QI": ["吸了口气", "缓了缓", "稳了稳气息"],
    # 子串型（regex 含 alternation）—— 通过 evidence 精确短语匹配执行
    "ZHONG_YU_MING_BAI": ["看清了", "想通了", "懂了", "明白过来"],
    "CONG_WEI_XIANG_GUO": ["没料到", "想不到", "没承想"],
}

# 这些 code 用删除而非替换
PHRASE_DELETIONS: set[str] = set()

# 不可执行（聚合 / 元信号），planner 直接跳过
NON_ACTIONABLE: set[str] = {
    "AI_CLICHE_OVERFLOW",
    "NOT_A_B_OVERFLOW",
    "SUMMARY_TONE",       # 多种短语聚合，无法精确替换
    "WATER_LOOK_REPEAT",  # 全段重写超 MVP 范围
    "WATER_SAY_REPEAT",
    "UNKNOWN",
}


def _seed_from(text: str, code: str) -> int:
    h = hashlib.sha256((code + text[:200]).encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big")


def _pick_replacement(text: str, code: str, options: list[str]) -> str:
    rng = random.Random(_seed_from(text, code))
    return rng.choice(options)


def plan(findings: Iterable[Finding], text: str) -> list[Action]:
    """聚合可执行 findings → 倒序排好的 action 列表。

    倒序排序的目的：executor 按 char_start 倒序应用，
    后面的替换不会影响前面 action 的 offset。
    """
    actions: list[Action] = []
    occupied_spans: list[tuple[int, int]] = []

    for f in findings:
        if f.code in NON_ACTIONABLE:
            continue
        if f.location is None or not f.location.has_offset():
            continue

        span = (f.location.char_start, f.location.char_end)

        # 跳过与已生成 action 重叠的位置
        if any(_overlaps(span, occ) for occ in occupied_spans):
            continue

        # 校验 location 指向的内容确实是 evidence（防 detector 报告位置漂移）
        actual = text[span[0]:span[1]]
        if f.evidence and actual != f.evidence:
            # 容错：尝试在附近窗口找
            continue

        action = _make_action(f, text)
        if action is None:
            continue
        actions.append(action)
        occupied_spans.append(span)

    # 倒序排序，executor 按此顺序应用
    actions.sort(key=lambda a: a.location.char_start, reverse=True)
    return actions


def _make_action(f: Finding, text: str) -> Action | None:
    span_text = text[f.location.char_start:f.location.char_end]
    if f.code in PHRASE_REPLACEMENTS:
        replacement = _pick_replacement(text, f.code, PHRASE_REPLACEMENTS[f.code])
        return Action(
            op=OP_REPLACE,
            location=f.location,
            args={"original": span_text, "replacement": replacement},
            source_findings=[f.code],
            reason=f"anti_ai套话 {f.code} → {replacement}",
        )
    if f.code in PHRASE_DELETIONS:
        return Action(
            op=OP_DELETE,
            location=f.location,
            args={"original": span_text},
            source_findings=[f.code],
            reason=f"删除 {f.code}",
        )
    return None


def _overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0])
