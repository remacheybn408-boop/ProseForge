#!/usr/bin/env python3
"""Merged detail agent."""

import re

from .base_analyzer import BaseAnalyzer


ACTION_VERBS = [
    re.compile(r"(抓|握|推|扶|扛|拎|捏|按|摸|拍|敲|抬|扯|挥|指|点|拨|攥|挪|撑)"),
    re.compile(r"(走|跑|退|进|转|停|站|坐|躺|俯|蹲|跃|避|闪|靠|倚|挪)"),
    re.compile(r"(看|望|瞥|盯|眯|瞪|扫量|注视|凝视)"),
    re.compile(r"(点头|摇头|耸肩|挥手|摆手|抬手|咬牙|握拳|抿嘴|皱眉|挑眉)"),
    re.compile(r"(叹|喘|笑|哭|咳|吞|咽|呼|吸)"),
    re.compile(r"(搬|抬|拽|扯|拖|拉|抱|推门|开门|关门)"),
    re.compile(r"(顿|愣|怔|僵|停|闷|闭|垂|抖)"),
]
STANDING_DIALOGUE_PATTERNS = [
    re.compile(r"(“[^”]{30,}”[^，。！？\n]{0,20}(说|问|道|答)?[，。！？]?)"),
    re.compile(r"(心想|心里|暗自|默默[^地])"),
]
SCENE_ANCHORS = [
    re.compile(r"(门|窗|墙|地|桌|椅|柜|床|梁|柱|砖|瓦|石板|青砖)"),
    re.compile(r"(火|灯|烛|月光|暗处|风|雨|雪|雷|雾)"),
    re.compile(r"(台阶|门槛|走廊|过道|转角|院子|天井|回廊|屋檐)"),
    re.compile(r"(草|树|根|枝|叶|泥|土|河|湖|山|崖|坑)"),
    re.compile(r"(书页|纸张|碗|杯|刀|剑|弓|简|符|匕首|棍)"),
    re.compile(r"(气味|声音|脚步|回声|水声|风声|柴火|火光|灶膛|霉味|潮湿)"),
]
SENSORY_DETAILS = [
    re.compile(r"(听见|听到|传来|响起|嗡嗡|咔嚓|咯吱|吱呀)"),
    re.compile(r"(闻到|气味|香味|腥味|焦味|药味|血腥|发霉|潮湿)"),
    re.compile(r"(冰凉|发冷|温热|粗糙|光滑|湿润|干涩|刺痛|发麻)"),
]
SCENE_TRANSITIONS = [
    re.compile(r"(走到|来到|回到|离开|走出|踏入|迈进|穿过|绕过)"),
    re.compile(r"(推开了门|关上了门|掀开了帘子|拨开了)"),
]
MUNDANE_MARKERS = [
    re.compile(r"(吃|饭|菜|喝|水|汤|茶|酒|粥|啃|咽|嘴干|肚子)"),
    re.compile(r"(穿上了|换上了|脱下了|披上了|系紧|拢了拢)"),
    re.compile(r"(擦汗|抹汗|挥去|汗水|额头|脸颊|手背)"),
    re.compile(r"(伤口处理|包扎|上药|止血|愈合|化脓|发炎|肿痛|疼)"),
    re.compile(r"(洗脸|洗手|漱口|刷牙|照镜子)"),
    re.compile(r"(睡觉|醒来了|眯眼|闭眼|困|倦乏|休息)"),
    re.compile(r"(烧火|点火|添柴|煮饭|熄火|灭火)"),
    re.compile(r"(煎药|熬药|喂药|抹药|药汁)"),
    re.compile(r"(钱|银子|铜板|便宜|贵|够不够|不够)"),
    re.compile(r"(鞋底|袜子|湿了|破了|衣衫|袖子|领口|裤脚)"),
    re.compile(r"(排队|领到|发了|派发|碗筷|勺子|馒头|米粥)"),
]
ABSTRACT_NOUNS = [
    re.compile(r"(命运|天道|法则|大道|因果|轮回|宿命|终极|本源|真理)"),
    re.compile(r"(巅峰|极致|无上|至高|最强|第一|至尊|不朽)"),
]


class DetailAnalyzer(BaseAnalyzer):
    """Merged detail/body/scene agent."""

    def __init__(self, config: dict = None):
        super().__init__(name="detail_agent", config=config)
        self.min_actions_per_500 = self.config.get("min_actions_per_500", 3)
        self.max_standing_paras = self.config.get("max_standing_paras", 5)
        self.min_sensory = self.config.get("min_sensory", 3)

    def review(self, content: str, chapter_no: int = 0, context: dict = None) -> dict:
        components = [
            self._review_body_action(content),
            self._review_scene_grounding(content),
            self._review_mundane_detail(content),
        ]
        return self._merge_components(components)

    def _review_body_action(self, content: str) -> dict:
        findings = []
        score = 60
        total_chars = len(content)

        action_count = sum(len(pattern.findall(content)) for pattern in ACTION_VERBS)
        actions_per_500 = action_count * 500 / max(total_chars, 1)
        if actions_per_500 < self.min_actions_per_500:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"动作密度偏低: {actions_per_500:.1f}/500字(需≥{self.min_actions_per_500})",
                    suggestion="增加手部动作、视线变化、身体位移和微表情",
                )
            )
            score -= 20
        elif actions_per_500 >= 8:
            score += 10

        standing_paras = sum(len(pattern.findall(content)) for pattern in STANDING_DIALOGUE_PATTERNS)
        if standing_paras > self.max_standing_paras:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"站桩对话/独白过多: {standing_paras}处",
                    suggestion="在长对白或独白中插入动作、停顿和环境反应",
                )
            )
            score -= 15

        body_keywords = [r"心跳", r"呼吸", r"手", r"腿", r"肩", r"背", r"喉咙", r"胸口", r"肚子", r"眼睛"]
        body_hits = sum(1 for keyword in body_keywords if re.search(keyword, content))
        if body_hits < 3:
            findings.append(
                self._make_finding(
                    "WARN",
                    "身体反应描写不足: 缺少心跳、呼吸或肌肉层面的反馈",
                    suggestion="增加生理反馈: 心跳加速、手心出汗、腿软、喉咙发干等",
                )
            )
            score -= 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)

    def _review_scene_grounding(self, content: str) -> dict:
        findings = []
        score = 60
        total_chars = max(len(content), 1)

        anchor_count = sum(len(pattern.findall(content)) for pattern in SCENE_ANCHORS)
        anchors_per_k = anchor_count * 1000 / total_chars
        if anchors_per_k < 8:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"场景物件稀薄: {anchors_per_k:.1f}/千字",
                    suggestion="增加具体物件: 门窗桌椅、台阶回廊、泥土草木、器物火光",
                )
            )
            score -= 20
        elif anchors_per_k >= 20:
            score += 10

        sensory_count = sum(len(pattern.findall(content)) for pattern in SENSORY_DETAILS)
        if sensory_count < self.min_sensory:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"感官细节不足: {sensory_count}处(需≥{self.min_sensory})",
                    suggestion="补充声音、气味和触感: 风声、药味、潮湿、冰凉、粗糙等",
                )
            )
            score -= 10

        transition_count = sum(len(pattern.findall(content)) for pattern in SCENE_TRANSITIONS)
        if transition_count > 6:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"场景切换过频: {transition_count}次",
                    suggestion="减少无必要的场景跳转，让读者在一个空间中停留更久",
                )
            )

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)

    def _review_mundane_detail(self, content: str) -> dict:
        findings = []
        score = 55
        total_chars = max(len(content), 1)

        mundane_count = sum(len(pattern.findall(content)) for pattern in MUNDANE_MARKERS)
        mundane_per_k = mundane_count * 1000 / total_chars
        if mundane_per_k < 4:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"生活细节缺失: {mundane_per_k:.1f}/千字",
                    suggestion="增加吃饭、换衣、擦汗、伤口处理、烧火和用钱等日常细节",
                )
            )
            score -= 25
        elif mundane_per_k >= 10:
            score += 10

        abstract_count = sum(len(pattern.findall(content)) for pattern in ABSTRACT_NOUNS)
        if abstract_count > 3:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"抽象大词过多({abstract_count}处): 命运、天道、极致等偏多",
                    suggestion="减少空泛概念，多用具体物件、动作和生活摩擦落地",
                )
            )
            score -= 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)
