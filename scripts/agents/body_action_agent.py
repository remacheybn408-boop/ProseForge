#!/usr/bin/env python3
"""body_action_agent.py — 动作自然度 Agent v0.6.5

检查人物是否只有站桩对话/心理独白，缺少身体动作。
"""
import re
from .base_agent import BaseAgent

# 动作动词
ACTION_VERBS = [
    re.compile(r'(抬|举|放|拿|抓|握|推|拉|按|捏|拍|敲|点|指|挥|摆|甩|扔|丢|捡|捧|端|递|接|收|藏|塞)'),
    re.compile(r'(走|跑|跳|跃|跨|迈|退|转|侧|蹲|跪|坐|站|躺|趴|靠|倚|扶|撑)'),
    re.compile(r'(看|望|瞥|瞟|盯|瞪|扫|环顾|打量|注视|凝视)'),
    re.compile(r'(点头|摇头|耸肩|挥手|摆手|搓手|攥拳|咬牙|握拳|抿嘴|皱眉|挑眉)'),
    re.compile(r'(吸|呼|喘|叹|咳|咽|吞|吐|抿|舔|咬)'),
    re.compile(r'(擦|抹|拭|拍|掸|扫|刷|洗|涮|冲)'),
    re.compile(r'(顿|停|愣|怔|僵|呆|凝|闪|缩|颤|抖)'),
]

# 纯对话/心理段落标记（缺少动作的段落）
STANDING_DIALOGUE_PATTERNS = [
    re.compile(r'(?:"[^"]{30,}"|「[^」]{30,}」|[^。]{30,}说[道]?[：:]?)'),  # 长对话无动作
    re.compile(r'(想[：:]|心想|心里|暗自|暗暗|默默[^地])'),  # 心理活动开头
]

class BodyActionAgent(BaseAgent):
    """动作自然度审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="body_action", config=config)
        self.min_actions_per_500 = self.config.get("min_actions_per_500", 3)
        self.max_standing_paras = self.config.get("max_standing_paras", 5)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 60
        total_chars = len(content)

        # 1. 动作动词密度
        action_count = 0
        action_details = []
        for pat in ACTION_VERBS:
            matches = pat.findall(content)
            action_count += len(matches)
            if matches:
                action_details.append((pat.pattern, len(matches)))

        actions_per_500 = action_count * 500 / max(total_chars, 1)

        if actions_per_500 < self.min_actions_per_500:
            findings.append(self._make_finding(
                "WARN", f"动作密度偏低: {actions_per_500:.1f}/500字 (需≥{self.min_actions_per_500})",
                suggestion="增加人物的手部动作、视线变化、身体位移、微表情等"))
            score -= 20
        elif actions_per_500 >= 8:
            score += 10

        # 2. 站桩对话检测
        standing_paras = 0
        for pat in STANDING_DIALOGUE_PATTERNS:
            standing_paras += len(pat.findall(content))

        if standing_paras > self.max_standing_paras:
            findings.append(self._make_finding(
                "WARN", f"站桩对话/独白段落过多: {standing_paras}处",
                suggestion="在长对话和独白中插入动作、停顿、环境反应，避免人物只说话不动"))
            score -= 15

        # 3. 身体反应缺失检测
        body_keywords = [r'心跳', r'呼吸', r'手', r'腿', r'肩', r'背', r'喉咙', r'胸口', r'肚子', r'眼睛']
        body_hits = sum(1 for kw in body_keywords if re.search(kw, content))
        if body_hits < 3:
            findings.append(self._make_finding(
                "WARN", "身体反应描写不足: 人物缺少心跳/呼吸/肌肉等生理反应",
                suggestion="增加身体反应: 心跳加速、呼吸变重、手心出汗、腿软、喉咙发干等"))
            score -= 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
