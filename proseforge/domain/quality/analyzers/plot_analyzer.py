#!/usr/bin/env python3
"""Merged plot agent."""

import re

from .base_analyzer import BaseAnalyzer


PROGRESS_MARKERS = [
    re.compile(r"(突破|升级|进阶|晋升|提升|进步)"),
    re.compile(r"(学会|掌握|领悟|参透|悟出|明白)"),
    re.compile(r"(发现|察觉|注意到|看出|认出|识破)"),
    re.compile(r"(得到|获得|拿到|取得|收获|收到)"),
    re.compile(r"(击败|打败|战胜|击退|击溃|制服)"),
    re.compile(r"(完成|结束|了结|解决|处理)"),
    re.compile(r"(变化|改变|转变|蜕变|质变)"),
    re.compile(r"(打脸|反转|逆转|翻盘|逆袭)"),
]
CONFLICT_MARKERS = [
    re.compile(r"(威压|压迫|镇压|压制|施压)"),
    re.compile(r"(冷笑|嘲讽|讥讽|讥笑|不屑|嗤笑)"),
    re.compile(r"(挑战|挑衅|约战|请战)"),
    re.compile(r"(危险|危机|凶险|致命|濒死|生死)"),
    re.compile(r"(冲突|对抗|对峙|对立|交锋)"),
    re.compile(r"(鄙夷|轻蔑|蔑视|看不起|瞧不起)"),
    re.compile(r"(打脸|翻盘|反转|逆袭)"),
]
PLEASURE_MARKERS = [
    re.compile(r"(震惊|愕然|惊诧|吃惊|难以置信)"),
    re.compile(r"(没想到|出乎意料|竟然|居然)"),
    re.compile(r"(跪拜|服服|佩服|刮目相看)"),
    re.compile(r"(打脸|当场打|面色大变|脸色一变)"),
    re.compile(r"(突破|晋升|升级|进阶)"),
    re.compile(r"(收获|奖励|宝物|法器|功法)"),
    re.compile(r"(谁敢|找死|不自量力)"),
]
ENDING_PRESSURE_MARKERS = [
    re.compile(r"(危险|危机|凶险|致命|陷阱)"),
    re.compile(r"(但|然而|不过)"),
    re.compile(r"(忽然|突然|猛然|骤然)"),
    re.compile(r"[？?]{1,3}\s*$", re.MULTILINE),
    re.compile(r"(不好|糟了|坏了|完了)"),
    re.compile(r"(冷笑|阴笑|诡异|神秘)"),
    re.compile(r"(到底|究竟)"),
]
HIGH_ENERGY = [
    re.compile(r"(打|杀|撞|砸|拳|爪|剑|刀|爆|炸|裂|碎|砍|刺|砸)"),
    re.compile(r"(怒|暴|吼|喝|叫|斥|骂|喊|吼叫)"),
    re.compile(r"(突破|升级|进阶|晋升|质变|蜕变|觉醒)"),
]
LOW_ENERGY = [
    re.compile(r"(看着|望着|注视|凝望|发呆|走神)"),
    re.compile(r"(坐下了|躺下了|靠在了|倚在了|身子一沉|停下)"),
    re.compile(r"(解释|说明|讲述|叙述|回忆|回想|想起)"),
]
FLAT_PATTERNS = re.compile(r"(又|再一次|继续|接着|然后|之后)")
PAYOFF_MARKERS = [
    re.compile(r"(果然|果真|不出所料|正如|印证|验证|证实|应验|实现)"),
    re.compile(r"(终于|总算|到头来|熬到|等到)"),
    re.compile(r"(兑现|偿还|履行|完成|达成|做到|办到)"),
    re.compile(r"(揭开|揭露|暴露|发现|真相|秘密|内幕|原来)"),
    re.compile(r"(回来|重返|再见|重逢)"),
]
NEW_THREADS_WITHOUT_PAYOFF = [
    re.compile(r"(约定|约好|说好|决定|打算|准备|将来|以后|等到.{0,10}(再|就))"),
    re.compile(r"(秘密|神秘|奇怪|诡异|不对|不对劲|有鬼|有诈)"),
    re.compile(r"(留下|遗留|残留|痕迹|线索|端倪)"),
]
COST_MARKERS = [
    re.compile(r"(受伤|流血|骨折|筋断|吐血|内脏|经脉|丹田|灵根|灵气)"),
    re.compile(r"(消耗|耗费|耗尽|透支|虚弱|疲惫|乏力|脱力|力竭)"),
    re.compile(r"(得罪|结仇|记恨|盯上|记下|记住|这笔账)"),
    re.compile(r"(欠下了|欠着人情|恩情|报答|偿还|还清|两清)"),
    re.compile(r"(副作用|后遗症|反噬|侵蚀|腐蚀|吞噬|损耗)"),
    re.compile(r"(代价|交换|付出|牺牲|舍弃|放弃|丢掉了)"),
    re.compile(r"(罚|扣|没收|收缴|上交|充公|扣除)"),
    re.compile(r"(记下了|登记|上报|记名|告状|检举)"),
]
WIN_WITHOUT_COST = [
    re.compile(r"(轻松|轻易|轻而不费|随手|随便|顺便|不经意)"),
    re.compile(r"(毫发无伤|毫发无损|轻松解决|轻易击败)"),
]


class PlotAnalyzer(BaseAnalyzer):
    """Merged plot/pacing/payoff/consequence agent."""

    def __init__(self, config: dict = None):
        super().__init__(name="plot_agent", config=config)
        self.min_progress = self.config.get("min_progress", 2)
        self.min_conflicts = self.config.get("min_conflicts", 1)
        self.min_pleasure = self.config.get("min_pleasure", 1)
        self.tail_chars = self.config.get("tail_chars", 600)
        self.min_payoffs = self.config.get("min_payoffs", 1)
        self.min_cost = self.config.get("min_cost", 3)

    def review(self, content: str, chapter_no: int = 0, context: dict = None) -> dict:
        components = [
            self._review_plot(content),
            self._review_pacing(content),
            self._review_payoff(content),
            self._review_consequence(content),
        ]
        return self._merge_components(components)

    def _review_plot(self, content: str) -> dict:
        findings = []
        score = 50

        progress_count = sum(len(pattern.findall(content)) for pattern in PROGRESS_MARKERS)
        if progress_count < self.min_progress:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"剧情推进不足: 仅检测到{progress_count}处推进标记",
                    evidence=f"需≥{self.min_progress}处",
                    suggestion="增加突破、发现、收获、击败等实质事件",
                )
            )
            score -= 20
        elif progress_count >= 5:
            score += 10

        conflict_count = sum(len(pattern.findall(content)) for pattern in CONFLICT_MARKERS)
        if conflict_count < self.min_conflicts:
            findings.append(
                self._make_finding(
                    "WARN",
                    "冲突/压力不足: 未检测到明显冲突标记",
                    suggestion="增加人际冲突、任务压力或外部威胁",
                )
            )
            score -= 15
        elif conflict_count >= 4:
            score += 5

        pleasure_count = sum(len(pattern.findall(content)) for pattern in PLEASURE_MARKERS)
        if pleasure_count < self.min_pleasure:
            findings.append(
                self._make_finding(
                    "WARN",
                    "爽点缺失: 未检测到打脸、反转、震惊或升级",
                    suggestion="每章至少给一个爽点: 打脸、突破、收获或围观震惊",
                )
            )
            score -= 15
        elif pleasure_count >= 3:
            score += 5

        tail = content[-self.tail_chars:] if len(content) > self.tail_chars else content
        ending_pressure = sum(1 for pattern in ENDING_PRESSURE_MARKERS if pattern.search(tail))
        if ending_pressure == 0:
            findings.append(
                self._make_finding(
                    "WARN",
                    "结尾无压力/钩子",
                    evidence=f"结尾{self.tail_chars}字无转折、悬念或危机信号",
                    suggestion="章节结尾应留下悬念或压力，驱动读者继续阅读",
                )
            )
            score -= 15
        elif ending_pressure >= 2:
            score += 5

        total_chars = len(content)
        if total_chars > 2000:
            mid_start = total_chars // 3
            mid_end = total_chars * 2 // 3
            mid_section = content[mid_start:mid_end]
            mid_progress = sum(1 for pattern in PROGRESS_MARKERS if pattern.search(mid_section))
            mid_conflict = sum(1 for pattern in CONFLICT_MARKERS if pattern.search(mid_section))
            if mid_progress == 0 and mid_conflict == 0:
                findings.append(
                    self._make_finding(
                        "WARN",
                        "中段空转: 章节中部无推进或冲突",
                        suggestion="中段至少保持一次推进、转折或冲突升级",
                    )
                )
                score -= 10

        chinese_count = self._count_chinese(content)
        if chinese_count < 1500:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"章节偏短: {chinese_count}字",
                    suggestion="建议每章保持在2000-4000字",
                )
            )
            score -= 5
        elif chinese_count > 8000:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"章节偏长: {chinese_count}字",
                    suggestion="建议拆章或精简，保持单章在5000字以内",
                )
            )

        score = max(0, min(100, score))
        status = "PASS" if score >= 80 else ("WARNING" if score >= 50 else "FAIL")
        return self._component_result(score, status, findings)

    def _review_pacing(self, content: str) -> dict:
        findings = []
        score = 60
        total_chars = len(content)

        high_count = sum(len(pattern.findall(content)) for pattern in HIGH_ENERGY)
        low_count = sum(len(pattern.findall(content)) for pattern in LOW_ENERGY)
        if high_count == 0 and total_chars > 1500:
            findings.append(
                self._make_finding(
                    "WARN",
                    "全章无高能段落: 缺少冲突、爆发、转折或进阶",
                    suggestion="即使不是战斗章，也应有情绪爆点或局势变化",
                )
            )
            score -= 20
        if low_count == 0 and total_chars > 1500:
            findings.append(
                self._make_finding(
                    "WARN",
                    "全章无停顿: 一直紧绷，没有呼吸空间",
                    suggestion="在高能段后插入短暂停顿: 观察、处理伤口、简短对白或回想",
                )
            )
            score -= 10

        flat_count = len(FLAT_PATTERNS.findall(content))
        flat_per_k = flat_count * 1000 / max(total_chars, 1)
        if flat_per_k > 15:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"连接词堆砌({flat_per_k:.0f}/千字): 节奏过平",
                    suggestion="减少'然后/接着/之后'，用动作和场景切换直接推进",
                )
            )

        if high_count > 0 and low_count > 0 and high_count + low_count > 10:
            score += 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)

    def _review_payoff(self, content: str) -> dict:
        findings = []
        score = 55

        payoff_count = sum(len(pattern.findall(content)) for pattern in PAYOFF_MARKERS)
        if payoff_count < self.min_payoffs:
            findings.append(
                self._make_finding(
                    "WARN",
                    "本章无兑现: 缺少果然、揭开、实现或回归式回报",
                    suggestion="每章至少兑现一个小承诺: 线索推进、谜面揭开或收获落地",
                )
            )
            score -= 20
        elif payoff_count >= 3:
            score += 10

        new_thread_count = sum(len(pattern.findall(content)) for pattern in NEW_THREADS_WITHOUT_PAYOFF)
        if new_thread_count > payoff_count + 2:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"开新坑({new_thread_count}处)远超兑现({payoff_count}处): 只挖不填",
                    suggestion="控制新伏笔数量，优先推进和兑现已有承诺",
                )
            )
            score -= 15

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)

    def _review_consequence(self, content: str) -> dict:
        findings = []
        score = 55

        cost_count = 0
        cost_types = set()
        for pattern in COST_MARKERS:
            matches = pattern.findall(content)
            cost_count += len(matches)
            if matches:
                cost_types.add(pattern.pattern[:20])

        if cost_count < self.min_cost:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"代价/后果不足: {cost_count}处(需≥{self.min_cost})",
                    suggestion="每个关键选择都应有后果: 受伤、消耗、得罪人、欠人情或被惩罚",
                )
            )
            score -= 25
        elif len(cost_types) >= 3:
            score += 15

        easy_count = sum(len(pattern.findall(content)) for pattern in WIN_WITHOUT_COST)
        if easy_count > 0:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"轻松取胜信号({easy_count}处): 没有代价的胜利容易发飘",
                    suggestion="给胜利加代价: 灵力消耗、受伤、暴露秘密或树敌",
                )
            )
            score -= 15

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)
