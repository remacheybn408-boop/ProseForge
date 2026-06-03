#!/usr/bin/env python3
"""pacing_breath_agent.py — 节奏呼吸 Agent v0.6.5

检查章节节奏: 是否一直紧绷或一直平，有无推进→停顿→爆点→余波→钩子的呼吸。
"""
import re
from .base_agent import BaseAgent

# 高能段落标记
HIGH_ENERGY = [
    re.compile(r'(打|战|拼|杀|冲|攻|破|爆|炸|裂|碎|毁|灭|崩|塌|倒)'),
    re.compile(r'(怒|暴|吼|喝|叱|斥|骂|喊|叫|吼|叱)'),
    re.compile(r'(突破|升级|进阶|晋升|质变|蜕变|觉醒)'),
]

# 低能/停顿段落标记
LOW_ENERGY = [
    re.compile(r'(看[着到见]|望[着到见]|注视|凝望|发呆|走神)'),
    re.compile(r'(坐[下了在]|蹲[下了在]|靠[在了]|倚[在了]|躺[下了在]|歇)'),
    re.compile(r'(解释|说明|讲述|叙述|回忆|回想|想起)'),
]

# 节奏问题
FLAT_PATTERNS = re.compile(r'(又|再[一次度]|继续|接着|然后|之后)')  # 推进乏力时多用连接词堆砌

class PacingBreathAgent(BaseAgent):
    """节奏呼吸审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="pacing_breath", config=config)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 60
        total_chars = len(content)

        # 1. 高能/低能比例
        high_count = sum(len(pat.findall(content)) for pat in HIGH_ENERGY)
        low_count = sum(len(pat.findall(content)) for pat in LOW_ENERGY)

        if high_count == 0 and total_chars > 1500:
            findings.append(self._make_finding(
                "WARN", "全章无高能段落: 缺少冲突、打斗、爆发或转折",
                suggestion="即使非战斗章也应有情绪爆点或冲突升级"))
            score -= 20

        if low_count == 0 and total_chars > 1500:
            findings.append(self._make_finding(
                "WARN", "全章无停顿: 一直紧绷没有呼吸空间",
                suggestion="在高能段落后插入短暂停顿: 观景/对话/回忆/处理伤口等"))
            score -= 10

        # 2. 连接词堆砌（节奏太平的信号）
        flat_count = len(FLAT_PATTERNS.findall(content))
        flat_per_k = flat_count * 1000 / max(total_chars, 1)
        if flat_per_k > 15:
            findings.append(self._make_finding(
                "WARN", f"连接词堆砌({flat_per_k:.0f}/千字): 节奏太平，像流水账",
                suggestion="减少'然后/接着/之后'，用场景切换和动作直接推进"))

        # 3. 理想节奏: 高能+低能都有
        if high_count > 0 and low_count > 0 and high_count + low_count > 10:
            score += 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
