#!/usr/bin/env python3
"""consequence_agent.py — 代价后果 Agent v0.6.5

检查事情发生后有没有代价和后果: 赢了有代价、受伤会持续、得罪人有后续。
"""
import re
from .base_agent import BaseAgent

# 代价标记
COST_MARKERS = [
    re.compile(r'(受伤|流血|骨折|筋断|吐血|内脏|经脉|丹田|灵根|灵气)'),
    re.compile(r'(消耗|耗费|耗尽|透支|虚弱|疲惫|乏力|脱力|力竭)'),
    re.compile(r'(得罪|结仇|记恨|盯上|记下|记住|这笔账)'),
    re.compile(r'(欠[下了]|债|人情|恩情|报答|偿还|还清|两清)'),
    re.compile(r'(副作用|后遗症|反噬|侵蚀|腐蚀|吞噬|损耗)'),
    re.compile(r'(代价|交换|付出|牺牲|舍弃|放弃|丢[掉了])'),
    re.compile(r'(罚|扣|没收|收缴|上交|充公|扣除)'),
    re.compile(r'(记[了下]名|登记|上报|禀告|告状|检举)'),
]

# 无代价信号
WIN_WITHOUT_COST = [
    re.compile(r'(轻松|轻易|轻而|不费|随手|随便|顺便|不经意)'),
    re.compile(r'(毫发无伤|毫发无损|轻松解决|轻易击败)'),
]

class ConsequenceAgent(BaseAgent):
    """代价后果审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="consequence", config=config)
        self.min_cost = self.config.get("min_cost", 3)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 55

        # 1. 代价检测
        cost_count = 0
        cost_types = set()
        for pat in COST_MARKERS:
            matches = pat.findall(content)
            cost_count += len(matches)
            if matches:
                cost_types.add(pat.pattern[:20])

        if cost_count < self.min_cost:
            findings.append(self._make_finding(
                "WARN", f"代价/后果不足: {cost_count}处 (需≥{self.min_cost})",
                suggestion="每个选择都应有后果: 受伤/消耗/得罪人/欠人情/被罚/记名"))
            score -= 25
        elif len(cost_types) >= 3:
            score += 15

        # 2. 轻松取胜检测
        easy_count = 0
        for pat in WIN_WITHOUT_COST:
            easy_count += len(pat.findall(content))

        if easy_count > 0:
            findings.append(self._make_finding(
                "WARN", f"轻松取胜信号({easy_count}处): 没有代价的胜利是AI写作常见病",
                suggestion="给胜利加代价: 消耗灵力、受伤、暴露秘密、得罪强者"))
            score -= 15

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
