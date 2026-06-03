#!/usr/bin/env python3
"""
continuity_agent.py — 连续性与一致性Agent v0.5.5

检查:
  1. 人物状态 — 伤势/灵力/境界/情绪是否与前文一致
  2. 物品跟踪 — 关键物品是否无故消失/出现
  3. 地点连续性 — 场景切换是否有过渡
  4. 任务线 — 进行中的任务是否被遗忘
  5. 伏笔回顾 — 长期伏笔是否在合理时机被提及

策略: 基于 prev_chapter context 做交叉比对
"""

import re
from .base_agent import BaseAgent

# ── 人物硬状态 ──
CHAR_STATE_MARKERS = {
    "伤势": re.compile(r'(伤口|流血|骨折|肿|青紫|绷带|包扎|伤势|残废)'),
    "灵力": re.compile(r'(灵力|法力|真气|修为|境界|筑基|金丹|元婴|化神)'),
    "情绪": re.compile(r'(恨|怒|怕|恐惧|悲伤|绝望|兴奋|期待|不安)'),
    "位置": re.compile(r'(被关|被困|禁闭|软禁|牢房|囚|锁|禁制)'),
}

# ── 关键物品 ──
KEY_ITEMS = [
    "止血丸", "柴刀", "役牌", "树皮", "粗陶碗", "草鞋",
    "木牌", "石碑", "令牌", "玉简", "法器", "丹药",
    "卷轴", "禁制符", "传送符", "信物", "残片", "密钥",
]

# ── 地点关键词 ──
LOCATION_KEYWORDS = [
    "院", "洞", "室", "殿", "阁", "楼", "厅", "堂",
    "巷", "街", "道", "山", "林", "矿", "坊", "市",
    "城", "镇", "村", "河", "湖", "海",
]

# ── 时间流逝标记 ──
TIME_PASSAGE = re.compile(
    r'(一炷香|一盏茶|半个时辰|一个时辰|半天|一天|一夜|'
    r'次日|第二天|几天后|数日后|一月后|半月)'
)


class ContinuityAgent(BaseAgent):
    """连续性与一致性审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="continuity_agent", config=config)
        self.strict_items = self.config.get("strict_items", True)
        self.strict_states = self.config.get("strict_states", True)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        context = context or {}
        prev_tail = context.get("prev_tail", "")
        prev_brief = context.get("prev_brief", {})
        first_chapter = (chapter_no <= 1)

        findings = []
        issues_count = 0

        content_start = content[:1000]

        if first_chapter:
            return self._build_result(0, "PASS", [])

        # ── 1. 人物状态延续 ──
        if prev_tail:
            tail = prev_tail[-500:]
            for state_name, pat in CHAR_STATE_MARKERS.items():
                prev_matches = pat.findall(tail)
                if not prev_matches:
                    continue
                curr_matches = pat.findall(content_start)
                if not curr_matches:
                    findings.append(self._make_finding(
                        "WARN", f"人物状态中断: {state_name}",
                        evidence=f"上章出现: {', '.join(list(set(prev_matches))[:3])}",
                        suggestion=f"确保{state_name}状态在本章开头被提及或说明变化"))
                    issues_count += 1

        # ── 2. 物品跟踪 ──
        if prev_tail:
            tail = prev_tail[-800:]
            prev_items = [item for item in KEY_ITEMS if item in tail]
            for item in prev_items:
                if item not in content:
                    # 只在关键物品上报警
                    if item in ["止血丸", "令牌", "玉简", "法器", "信物", "残片"]:
                        findings.append(self._make_finding(
                            "WARN", f"关键物品失踪: '{item}'",
                            evidence=f"上章结尾出现, 本章全文未见",
                            suggestion=f"说明'{item}'的去向或在本章中出现"))
                        issues_count += 1

        # ── 3. 地点连续性 ──
        if prev_tail:
            tail_end = prev_tail[-300:]
            prev_locations = list(set(
                kw for kw in LOCATION_KEYWORDS if kw in tail_end))
            curr_locations = list(set(
                kw for kw in LOCATION_KEYWORDS if kw in content_start))

            if prev_locations and curr_locations:
                overlap = set(prev_locations) & set(curr_locations)
                if not overlap:
                    # 检查是否有过渡
                    has_transition = any(w in content_start for w in
                                         ['离开', '走到', '来到', '回到', '踏入',
                                          '进入', '穿过', '翻过', '越过', '经过'])
                    if not has_transition:
                        findings.append(self._make_finding(
                            "WARN", "地点跳跃无过渡",
                            evidence=f"上章: {prev_locations}, 本章: {curr_locations}",
                            suggestion="增加转场描写: 离开→路途→到达"))
                        issues_count += 1

        # ── 4. 任务线 ──
        task_continuity = context.get("task_continuity", "")
        if task_continuity and task_continuity not in content[:1500]:
            findings.append(self._make_finding(
                "WARN", "任务线中断",
                evidence=f"任务'{task_continuity[:60]}'在本章前半未见",
                suggestion="在章节前部提及或推进进行中的任务"))

        # ── 5. 伏笔回顾 ──
        foreshadowing = context.get("foreshadowing", [])
        if foreshadowing:
            recalled = 0
            for fs in foreshadowing:
                keywords = re.findall(r'[\u4e00-\u9fff]{2,4}', fs.get("text", ""))
                if any(kw in content for kw in keywords):
                    recalled += 1
            # 不强制要求每章回顾伏笔, 仅信息通报
            pass

        # ── 6. 时间一致性 ──
        # 检查是否有时间矛盾: 夜晚对话后立即天亮无过渡
        night_markers = ['夜里', '夜晚', '深夜', '半夜', '夜幕']
        day_markers = ['清晨', '天亮', '早晨', '上午', '中午', '午后', '下午']
        has_night = any(m in prev_tail[-300:] for m in night_markers) if prev_tail else False
        has_day = any(m in content_start[:300] for m in day_markers)
        if has_night and has_day:
            if not TIME_PASSAGE.search(content_start[:200]):
                findings.append(self._make_finding(
                    "WARN", "时间跳转无标记: 上章夜晚→本章清晨无过渡",
                    suggestion="添加'一夜过去'/'次日清晨'等时间过渡"))

        # ── 裁决 ──
        if issues_count == 0:
            score = 0
            status = "PASS"
        elif issues_count <= 2:
            score = 30 + issues_count * 10
            status = "WARNING"
        else:
            score = 50 + issues_count * 10
            status = "WARNING"

        return self._build_result(score, status, findings)
