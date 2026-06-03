#!/usr/bin/env python3
"""subtext_agent.py — 潜台词 Agent v0.6.5

检查对话是否太直白: 人物把心里话全说出来、直接解释动机、缺少遮掩。
"""
import re
from .base_agent import BaseAgent

# 直白解释模式
EXPLICIT_EXPLAIN = [
    re.compile(r'(因为.{1,20}所以)'),  # 直接因果
    re.compile(r'(其实.{1,30}是[因为])'),  # 解释动机
    re.compile(r'(我[就才]?是[因为].{1,20})'),  # 直接承认动机
    re.compile(r'(你[不]?知道.{1,20}[因为])'),  # 解释给对方听
    re.compile(r'(坦白说|老实说|说白了|说实话|不瞒你)'),  # 直接坦白的信号
    re.compile(r'(我[^，。]{0,10}(在乎|关心|担心|害怕|喜欢|恨|讨厌)[^，。]{0,20}[你我他她它])'),  # 直接情感表达
]

# 遮掩/试探/反讽标记（好的潜台词）
SUBTEXT_GOOD = [
    re.compile(r'(冷笑|哼|嗤|啧|呵|切)'),  # 用态度代替直接表达
    re.compile(r'(别过[脸头]|偏过[头脸]|不看|避开|垂[下眼目])'),  # 身体回避代替语言
    re.compile(r'(顿[了顿]|停了[一下停]|沉默了|没说[话])'),  # 停顿代替直接说
    re.compile(r'(随便|无所谓|你定|都行|算了|没事)'),  # 嘴上说无所谓其实在意
]

class SubtextAgent(BaseAgent):
    """潜台词审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="subtext", config=config)
        self.max_explicit = self.config.get("max_explicit", 5)
        self.min_subtext = self.config.get("min_subtext", 3)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 60
        total_chars = max(len(content), 1)

        # 1. 直白解释检测
        explicit_count = 0
        for pat in EXPLICIT_EXPLAIN:
            matches = pat.findall(content)
            if matches:
                explicit_count += len(matches)
                findings.append(self._make_finding(
                    "WARN", f"对话过于直白: '{matches[0][:40] if isinstance(matches[0], str) else str(matches[0])[:40]}'",
                    evidence=matches[0][:80] if isinstance(matches[0], str) else str(matches[0])[:80],
                    suggestion="人物不必说出全部心里话; 用行动、停顿、反话代替直接表达"))

        explicit_per_k = explicit_count * 1000 / total_chars
        if explicit_per_k > 4:
            score -= 25
        elif explicit_count > self.max_explicit:
            score -= 15

        # 2. 潜台词技巧检测
        subtext_count = 0
        for pat in SUBTEXT_GOOD:
            subtext_count += len(pat.findall(content))

        if subtext_count < self.min_subtext:
            findings.append(self._make_finding(
                "WARN", f"潜台词技巧不足: {subtext_count}处 (需≥{self.min_subtext})",
                suggestion="增加冷笑/别过头/沉默/说反话等间接表达"))
            score -= 10
        elif subtext_count >= 8:
            score += 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
