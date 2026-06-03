#!/usr/bin/env python3
"""emotion_curve_agent.py — 情绪递进 Agent v0.6.5

检查情绪是否跳跃太快: 上一秒平静下一秒暴怒，缺少过渡。
"""
import re
from .base_agent import BaseAgent

# 情绪爆发标记（需要前面有铺垫）
EMOTION_BURSTS = [
    re.compile(r'(暴怒|大怒|狂怒|愤怒|怒极|怒不可遏|勃然大怒)'),
    re.compile(r'(崩溃|垮掉|决堤|失控|失声|嚎啕)'),
    re.compile(r'(感动|哽咽|泪流|红了眼眶|鼻子一酸)'),
    re.compile(r'(顿悟|豁然|恍然|醒悟|一下子明白)'),
]

# 情绪过渡标记（好的铺垫）
EMOTION_BUILDUP = [
    re.compile(r'(隐隐|渐渐|慢慢|逐渐|一点点|越来越)'),
    re.compile(r'(压下|强忍|憋着|按住|攥[紧拳]|咬[牙唇])'),  # 压制情绪
    re.compile(r'(不安|不对|不好|不妙|不对劲)'),  # 情绪起点
    re.compile(r'(深吸|呼出|叹了|吐了)'),  # 情绪调节
]

# 情绪标签（只有标签没有过程）
EMOTION_LABELS = [
    re.compile(r'(很(高兴|难过|震惊|生气|失望|感动|害怕|紧张|焦虑|兴奋|激动))'),
    re.compile(r'(非常(高兴|难过|震惊|生气|失望|感动|害怕|紧张|焦虑|兴奋|激动))'),
    re.compile(r'(极度(高兴|难过|震惊|生气|失望|感动|害怕|紧张|焦虑|兴奋|激动))'),
]

class EmotionCurveAgent(BaseAgent):
    """情绪递进审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="emotion_curve", config=config)
        self.min_buildup_per_burst = self.config.get("min_buildup_per_burst", 1)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 60

        # 1. 情绪爆发检测
        burst_count = 0
        burst_samples = []
        for pat in EMOTION_BURSTS:
            matches = pat.findall(content)
            burst_count += len(matches)
            if matches:
                burst_samples.append(matches[0][:40])

        # 2. 情绪铺垫检测
        buildup_count = 0
        for pat in EMOTION_BUILDUP:
            buildup_count += len(pat.findall(content))

        # 3. 情绪标签检测
        label_count = 0
        label_samples = []
        for pat in EMOTION_LABELS:
            matches = pat.findall(content)
            label_count += len(matches)
            if matches:
                label_samples.append(str(matches[0])[:40])

        # 评分
        if label_count >= 3:
            findings.append(self._make_finding(
                "WARN", f"情绪标签过多({label_count}处): 只贴标签不写过程",
                evidence=str(label_samples[:3]),
                suggestion="删掉'很震惊''非常感动'等标签，用身体反应和行为来展现情绪"))
            score -= 20

        if burst_count > 0 and buildup_count < burst_count * self.min_buildup_per_burst:
            findings.append(self._make_finding(
                "WARN", f"情绪跳跃: {burst_count}处爆发, 仅{buildup_count}处铺垫",
                evidence=str(burst_samples[:3]),
                suggestion="情绪爆发前应有过渡: 不安→忍耐→爆发, 或 疑惑→紧张→恐慌"))
            score -= 15
        elif buildup_count >= 6:
            score += 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
