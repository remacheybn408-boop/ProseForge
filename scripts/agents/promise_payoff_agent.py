#!/usr/bin/env python3
"""promise_payoff_agent.py — 承诺兑现 Agent v0.6.5

检查前文钩子/伏笔/承诺在本章有无小兑现。
与 reader_pull（看追读感）不同，本Agent专注于"说过的事有没有做"。
"""
import re
from .base_agent import BaseAgent

# 兑现信号
PAYOFF_MARKERS = [
    re.compile(r'(果然|果真|不出所料|正如|印证|验证|证实|应验|实现)'),
    re.compile(r'(终于|总算|到底|到头来|熬到|等到)'),
    re.compile(r'(兑现|偿还|履行|完成|达成|做到|办到)'),
    re.compile(r'(揭开|揭露|暴露|发现|真相|秘密|内幕|原来)'),
    re.compile(r'(回来[了到]|归[来了还]|重返|再[见次]|重逢|见到)'),
]

# 只开新坑不填的信号
NEW_THREADS_WITHOUT_PAYOFF = [
    re.compile(r'(约定|约好|说好|决定|打算|准备|将来|以后|等[到].{0,10}[再就])'),
    re.compile(r'(秘密|神秘|奇怪|诡异|不对|不对劲|有鬼|有诈)'),
    re.compile(r'(留下|遗留|残[留存余]|痕迹|线索|端倪)'),
]

class PromisePayoffAgent(BaseAgent):
    """承诺兑现审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="promise_payoff", config=config)
        self.min_payoffs = self.config.get("min_payoffs", 1)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 55

        # 1. 兑现检测
        payoff_count = 0
        payoff_samples = []
        for pat in PAYOFF_MARKERS:
            matches = pat.findall(content)
            payoff_count += len(matches)
            if matches:
                payoff_samples.append(str(matches[0])[:40])

        if payoff_count < self.min_payoffs:
            findings.append(self._make_finding(
                "WARN", f"本章无兑现: 0处'果然/终于/揭开/回来'等兑现信号",
                suggestion="每章至少兑现一个小承诺: 前文提到的约定/秘密/线索有一点进展"))
            score -= 20
        elif payoff_count >= 3:
            score += 10

        # 2. 新坑检测（只开不填）
        new_thread_count = 0
        for pat in NEW_THREADS_WITHOUT_PAYOFF:
            new_thread_count += len(pat.findall(content))

        if new_thread_count > payoff_count + 2:
            findings.append(self._make_finding(
                "WARN", f"开新坑({new_thread_count}处)远超兑现({payoff_count}处): 只挖坑不填",
                suggestion="控制新伏笔数量，优先推进和兑现已有伏笔"))
            score -= 15

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
