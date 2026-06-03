#!/usr/bin/env python3
"""scene_grounding_agent.py — 场景落地 Agent v0.6.5

检查场景是否有真实物件和空间感，避免"白房间"写作。
"""
import re
from .base_agent import BaseAgent

# 场景锚点物件
SCENE_ANCHORS = [
    re.compile(r'(门|窗|墙|地|桌|椅|凳|床|榻|柜|架|箱|缸|桶|碗|杯|壶|锅|灶|炉|炕|砖|瓦|木|石|石板|青砖)'),
    re.compile(r'(灯|烛|火|光|影|暗|阴|凉|暖|热|冷|风|雨|雪|雾|霜|露)'),
    re.compile(r'(台阶|门槛|走廊|过道|转角|院|庭|天井|回廊|屋檐|檐下)'),
    re.compile(r'(草|树|叶|枝|花|藤|苔|泥|土|沙|石|岩|崖|坡|沟|坑)'),
    re.compile(r'(书|笔|纸|墨|砚|卷|册|简|符|阵|法器|丹|药|炉|鼎|剑|刀|枪|棍)'),
    re.compile(r'(气味|声音|脚步|回声|水声|风声|柴火|炭|烟|灰|尘|蛛网|霉)'),
]

# 声音/气味/触感等感官细节
SENSORY_DETAILS = [
    re.compile(r'(听见|听到|传来|响起|嗡嗡|呼呼|啪|砰|咚|咯吱|嘎吱)'),
    re.compile(r'(闻到|气味|香味|臭味|腥味|焦味|药味|血腥|发霉|潮湿)'),
    re.compile(r'(凉|冷|冰|烫|热|温|粗糙|光滑|湿|干|硬|软|黏|滑|刺|扎)'),
]

# 场景切换标记
SCENE_TRANSITIONS = [
    re.compile(r'(走[到进]|来[到进]|去[到进]|回到|离开|走出|踏入|迈进|穿过|绕过)'),
    re.compile(r'(推[开了]门|敲[门了]|掀[开了]帘|撩[开了])'),
]

class SceneGroundingAgent(BaseAgent):
    """场景落地审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="scene_grounding", config=config)
        self.min_anchors = self.config.get("min_anchors", 8)
        self.min_sensory = self.config.get("min_sensory", 3)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 60
        total_chars = max(len(content), 1)

        # 1. 场景锚点密度
        anchor_count = 0
        for pat in SCENE_ANCHORS:
            anchor_count += len(pat.findall(content))

        anchors_per_k = anchor_count * 1000 / total_chars
        if anchors_per_k < 8:
            findings.append(self._make_finding(
                "WARN", f"场景物件稀疏: {anchors_per_k:.1f}/千字",
                suggestion="增加具体物件: 桌椅门窗、灯烛火光、台阶门槛、草木泥土等"))
            score -= 20
        elif anchors_per_k >= 20:
            score += 10

        # 2. 感官细节
        sensory_count = 0
        for pat in SENSORY_DETAILS:
            sensory_count += len(pat.findall(content))
        if sensory_count < self.min_sensory:
            findings.append(self._make_finding(
                "WARN", f"感官细节不足: {sensory_count}处 (需≥{self.min_sensory})",
                suggestion="增加声音/气味/触感: 风声、脚步、焦味、冰凉、粗糙等"))
            score -= 10

        # 3. 场景切换
        transition_count = 0
        for pat in SCENE_TRANSITIONS:
            transition_count += len(pat.findall(content))

        if transition_count > 6:
            findings.append(self._make_finding(
                "WARN", f"场景切换过频: {transition_count}次",
                suggestion="减少场景跳跃，让读者在一个场景里停留足够长"))

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
