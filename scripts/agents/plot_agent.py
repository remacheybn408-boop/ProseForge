#!/usr/bin/env python3
"""
plot_agent.py — 剧情推进/冲突Agent v0.5.5

检查:
  1. 剧情推进 — 本章是否有实质性进展 (非原地踏步)
  2. 冲突强度 — 是否有冲突/压力, 是否升级
  3. 爽点 — 是否有打脸/反转/破解/收获/升级
  4. 结尾压力 — 章节结尾是否留下压力/钩子
  5. 节奏 — 是否长时间无推进 (检查中段空转)

策略: 关键词+段落结构分析
"""

import re
from .base_agent import BaseAgent

# ── 实质性推进标记 ──
PROGRESS_MARKERS = [
    re.compile(r'(突破|升级|进阶|晋升|提升|进步)'),
    re.compile(r'(学会|掌握|领悟|参透|悟出|明白)'),
    re.compile(r'(发现|察觉|注意到|看出|认出|识破)'),
    re.compile(r'(得到|获得|拿到|取得|收获|收到)'),
    re.compile(r'(击败|打败|战胜|击退|击溃|制服)'),
    re.compile(r'(完成|结束|了结|解决|处理)'),
    re.compile(r'(变化|改变|转变|蜕变|质变)'),
    re.compile(r'(打脸|反转|逆转|翻盘|逆袭)'),
]

# ── 冲突/压力标记 ──
CONFLICT_MARKERS = [
    re.compile(r'(威压|压迫|镇压|压制|施压)'),
    re.compile(r'(冷笑|嘲讽|讥讽|讥笑|不屑|嗤笑)'),
    re.compile(r'(挑战|挑衅|邀战|约战|请战)'),
    re.compile(r'(危险|危机|凶险|致命|濒死|生死)'),
    re.compile(r'(冲突|对抗|对峙|对立|交锋)'),
    re.compile(r'(鄙夷|轻蔑|蔑视|看不起|瞧不起)'),
    re.compile(r'(打脸|翻盘|反转|逆袭)'),
]

# ── 爽点标记 ──
PLEASURE_MARKERS = [
    re.compile(r'(震惊|愕然|惊讶|吃惊|难以置信)'),
    re.compile(r'(没想到|出乎意料|竟然|居然)'),
    re.compile(r'(跪|拜服|佩服|刮目相看)'),
    re.compile(r'(啪啪啪|打脸|当场打|面色大变|脸色一变)'),
    re.compile(r'(突破|晋升|升级|进阶)'),
    re.compile(r'(收获|奖励|宝物|法器|功法)'),
    re.compile(r'(谁敢|找死|不自量力)'),  # 主角霸气
]

# ── 结尾压力/钩子标记 ──
ENDING_PRESSURE_MARKERS = [
    re.compile(r'(危险|危机|凶险|致命|陷阱)'),
    re.compile(r'(却|但|然而|可|不过)'),  # 结尾转折
    re.compile(r'(忽然|突然|猛然|骤然)'),  # 突发事件
    re.compile(r'[？?]{1,3}\s*$', re.MULTILINE),  # 疑问结尾
    re.compile(r'(不好|糟了|坏了|完了)'),
    re.compile(r'(冷笑|阴笑|诡异|神秘)'),
    re.compile(r'(到底|究竟)'),
]

# ── 原地踏步标记 ──
STAGNATION_MARKERS = [
    re.compile(r'(无聊|没劲|没意思)'),
    re.compile(r'(发呆|走神|出神|神游)'),
    re.compile(r'(\S{1,3})又(\S{1,3})'),  # 看了又看, 走了又走
]


class PlotAgent(BaseAgent):
    """剧情推进审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="plot_agent", config=config)
        self.min_progress = self.config.get("min_progress", 2)
        self.min_conflicts = self.config.get("min_conflicts", 1)
        self.min_pleasure = self.config.get("min_pleasure", 1)
        self.tail_chars = self.config.get("tail_chars", 600)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 50  # start at 50, deduct for problems
        max_score = 100
        min_score = 0

        # ── 1. 剧情推进检测 ──
        progress_count = 0
        progress_details = []
        for pat in PROGRESS_MARKERS:
            matches = pat.findall(content)
            if matches:
                progress_count += len(matches)
                progress_details.extend(matches[:3])

        if progress_count < self.min_progress:
            findings.append(self._make_finding(
                "WARN", f"剧情推进不足: 仅检测到{progress_count}处推进标记",
                evidence=f"需≥{self.min_progress}处",
                suggestion="增加突破/发现/收获/击败等实质性事件"))
            score -= 20
        elif progress_count >= 5:
            score += 10

        # ── 2. 冲突/压力检测 ──
        conflict_count = 0
        for pat in CONFLICT_MARKERS:
            matches = pat.findall(content)
            if matches:
                conflict_count += len(matches)

        if conflict_count < self.min_conflicts:
            findings.append(self._make_finding(
                "WARN", "冲突/压力不足: 未检测到明显冲突标记",
                suggestion="增加人际冲突、任务压力或外部威胁"))
            score -= 15
        elif conflict_count >= 4:
            score += 5

        # ── 3. 爽点检测 ──
        pleasure_count = 0
        for pat in PLEASURE_MARKERS:
            matches = pat.findall(content)
            if matches:
                pleasure_count += len(matches)

        if pleasure_count < self.min_pleasure:
            findings.append(self._make_finding(
                "WARN", "爽点缺失: 未检测到打脸/反转/震惊/升级",
                suggestion="每章至少1个爽点: 打脸/震惊围观/突破/收获"))
            score -= 15
        elif pleasure_count >= 3:
            score += 5

        # ── 4. 结尾压力检测 ──
        tail = content[-self.tail_chars:] if len(content) > self.tail_chars else content
        ending_pressure = 0
        for pat in ENDING_PRESSURE_MARKERS:
            matches = pat.findall(tail)
            if matches:
                ending_pressure += 1

        if ending_pressure == 0:
            findings.append(self._make_finding(
                "WARN", "结尾无压力/钩子",
                evidence=f"结尾{self.tail_chars}字无转折/悬念/危机信号",
                suggestion="章节结尾应留有悬念或压力, 驱动读者继续阅读"))
            score -= 15
        elif ending_pressure >= 2:
            score += 5

        # ── 5. 节奏检测: 中段空转 ──
        total_chars = len(content)
        if total_chars > 2000:
            mid_start = total_chars // 3
            mid_end = total_chars * 2 // 3
            mid_section = content[mid_start:mid_end]

            mid_progress = sum(1 for pat in PROGRESS_MARKERS if pat.search(mid_section))
            mid_conflict = sum(1 for pat in CONFLICT_MARKERS if pat.search(mid_section))

            if mid_progress == 0 and mid_conflict == 0:
                findings.append(self._make_finding(
                    "WARN", "中段空转: 章节中部(1/3~2/3)无推进/冲突",
                    suggestion="中段应至少保持推进或冲突, 避免纯过渡/描写"))
                score -= 10

        # ── 6. 章节长度 ──
        chinese_count = self._count_chinese(content)
        if chinese_count < 1500:
            findings.append(self._make_finding(
                "WARN", f"章节偏短: {chinese_count}字",
                suggestion="建议每章2000-4000字"))
            score -= 5
        elif chinese_count > 8000:
            findings.append(self._make_finding(
                "WARN", f"章节偏长: {chinese_count}字",
                suggestion="建议拆分或精简, 保持单章≤5000字为佳"))

        # ── 裁决 ──
        score = max(min_score, min(max_score, score))

        if score >= 80:
            status = "PASS"
        elif score >= 50:
            status = "WARNING"
        else:
            status = "FAIL"

        return self._build_result(score, status, findings)
