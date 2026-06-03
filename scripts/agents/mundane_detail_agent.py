#!/usr/bin/env python3
"""mundane_detail_agent.py — 生活细节 Agent v0.6.5

检查是否有日常生活的烟火气: 吃饭、换衣、擦汗、伤口处理、柴火不够等。
"""
import re
from .base_agent import BaseAgent

# 生活细节标记
MUNDANE_MARKERS = [
    re.compile(r'(吃[饭了菜]|喝[水汤茶酒粥]|啃|嚼|咽|吞|饱|饿|饥|渴|口干|肚子)'),
    re.compile(r'(穿[衣上]|换[衣了]|脱[下了]|披[上了]|裹|系|系紧|扎|绑|勒)'),
    re.compile(r'(擦[汗了]|抹[汗了]|拭[去了]|汗水|额头|脸颊|手背)'),
    re.compile(r'(伤[口处]|包扎|上药|止血|愈合|化脓|发炎|肿|疼|痛|疤)'),
    re.compile(r'(洗[脸手澡]|刷[牙洗]|梳|理|剃|刮|照[镜子])'),
    re.compile(r'(睡[觉下]|醒[来了]|睁眼|闭眼|困|倦|乏|累|喘|歇|休息)'),
    re.compile(r'(柴[火草]|炭|煤|烧[水火饭]|煮|炖|蒸|炒|熬|热[了一]|冷[了掉]|凉)'),
    re.compile(r'(药[丸散膏汤]|熬药|煎药|喂药|服[药了]|苦|涩)'),
    re.compile(r'(钱|银|铜|欠|赊|当|卖|买|换|贵|便宜|够不够|不够)'),
    re.compile(r'(鞋[子底]|湿|潮|破|补|缝|针线|布|衣裳|袖子|领口|裤脚)'),
    re.compile(r'(排队|领|分[发了]|派|发放|碗筷|勺子|馒头|粥|稀)'),
]

# 抽象大词（缺生活细节的信号）
ABSTRACT_NOUNS = [
    re.compile(r'(命运|天道|法则|大道|因果|轮回|宿命|终极|本源|真理)'),
    re.compile(r'(巅峰|极致|无上|至高|最强|第一|至尊|不朽)'),
]

class MundaneDetailAgent(BaseAgent):
    """生活细节审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="mundane_detail", config=config)
        self.min_mundane = self.config.get("min_mundane", 5)
        self.max_abstract = self.config.get("max_abstract", 3)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 55
        total_chars = max(len(content), 1)

        # 1. 生活细节密度
        mundane_count = 0
        for pat in MUNDANE_MARKERS:
            mundane_count += len(pat.findall(content))

        mundane_per_k = mundane_count * 1000 / total_chars
        if mundane_per_k < 4:
            findings.append(self._make_finding(
                "WARN", f"生活细节缺失: {mundane_per_k:.1f}/千字",
                suggestion="增加吃饭、换衣、擦汗、伤口、柴火、药钱等日常细节"))
            score -= 25
        elif mundane_per_k >= 10:
            score += 10

        # 2. 大词检测
        abstract_count = 0
        for pat in ABSTRACT_NOUNS:
            abstract_count += len(pat.findall(content))

        if abstract_count > self.max_abstract:
            findings.append(self._make_finding(
                "WARN", f"抽象大词过多({abstract_count}处): 命运/天道/巅峰/终极",
                suggestion="减少空泛概念，用具体物件和行为代替"))
            score -= 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._build_result(score, status, findings)
