#!/usr/bin/env python3
"""Merged continuity agent."""

import re

from .base_analyzer import BaseAnalyzer


HARD_INJURY_RE = re.compile(
    r"(伤口|流血|骨折|淤青|紫|绷带|包扎|敷药|治疗|养伤|伤势|断臂|残废|濒死|晕厥|眩晕|头晕|昏迷|中毒|血痕|渗血|破皮)"
)
HARD_TRAPPED_RE = re.compile(r"(被困|锁住|封住|困在|困入|禁锢|无法离开)")
HARD_CRITICAL_ITEM_RE = re.compile(
    r"(止血丹|玉简|令牌|法器|关键丹药|关键证物|证物|残片|密钥|卷轴|禁制符|传送符|信物)"
)
HARD_LIFE_DEATH_RE = re.compile(r"(死亡|濒死|追杀|生死危机|处刑|审判|毙命|绝境|垂死|将死)")

VACUUM_TRANSITION_WORDS = {
    "回到", "来到", "走进", "踏入", "走到", "经过", "一路", "穿过",
    "翻过", "顺着", "沿着", "赶路", "出发", "离开", "转场",
}
TIME_JUMP_MARKERS = {
    "次日", "第二天", "翌日", "明日", "今天", "今日", "当晚", "当夜", "第二日",
    "半月后", "一个月后", "三月后", "半年后", "数日之后", "几天后",
}
SUDDEN_CHAR_PATTERN = re.compile(
    r"(一个.{0,4}(?:人|弟子|师兄|师姐|长老|执事|掌柜|老者|少年|女子|男子|修士|散修).{0,6}(?:走来|站着|出现|拦|拦住|叫|喝|说|问|道))"
)

CHAR_STATE_MARKERS = {
    "伤势": re.compile(r"(伤口|流血|骨折|淤青|绷带|包扎|伤势|残废)"),
    "灵力": re.compile(r"(灵力|法力|真气|修为|境界|筑基|金丹|元婴|化神)"),
    "情绪": re.compile(r"(愤怒|恼怒|恐惧|悲伤|绝望|兴奋|期待|不安)"),
    "位置": re.compile(r"(被关|被困|禁闭|软禁|牢房|囚禁|锁住|禁制)"),
}
KEY_ITEMS = [
    "止血丹", "柴刀", "腰牌", "树皮", "粗陶碗", "草鞋",
    "木牌", "石碗", "令牌", "玉简", "法器", "丹药",
    "卷轴", "禁制符", "传送符", "信物", "残片", "密钥",
]
LOCATION_KEYWORDS = [
    "院", "洞", "屋", "殿", "阁", "楼", "庙", "堂", "坊", "街",
    "道", "山", "林", "矿", "坑", "池", "城", "塔", "桥", "河",
    "湖", "海",
]
TIME_PASSAGE = re.compile(
    r"(一炷香|一盏茶|半个时辰|一个时辰|半天|一天|次日|第二天|几天后|数日后|一月后|半月)"
)


class ContinuityAnalyzer(BaseAnalyzer):
    """Merged continuity/context agent."""

    def __init__(self, config: dict = None):
        super().__init__(name="continuity_agent", config=config)
        self.min_bridge_score = self.config.get("min_bridge_score", 4)
        self.tail_lookback = self.config.get("tail_lookback", 400)

    def review(self, content: str, chapter_no: int = 0, context: dict = None) -> dict:
        context = context or {}
        components = [
            self._review_context(content, chapter_no, context),
            self._review_continuity(content, chapter_no, context),
        ]
        return self._merge_components(components)

    def _review_context(self, content: str, chapter_no: int, context: dict) -> dict:
        prev_tail = context.get("prev_tail", "")
        prev_hooks = context.get("prev_hooks", [])
        prev_brief = context.get("prev_brief", {})
        first_chapter = chapter_no <= 1

        findings = []
        bridge_score = 0

        content_start = content[:1200]
        content_head = content[:600]

        if prev_tail and not first_chapter:
            tail = prev_tail[-self.tail_lookback:] if len(prev_tail) > self.tail_lookback else prev_tail
            action_kws = set(
                re.findall(
                    r"(动作|砸|推|搬|拽|扛|挨|挖|跑|走|站|坐|说|问|答|叫|看|盯|摸|抓|抬|扯|打|考核|验收|登记)",
                    tail,
                )
            )
            matched = [kw for kw in action_kws if kw in content_head]
            bridge_score += min(3, len(matched))
            if not matched and action_kws:
                findings.append(
                    self._make_finding(
                        "WARN",
                        "上一章动作未延续",
                        evidence=f"上章尾部关键词: {', '.join(list(action_kws)[:8])}",
                        suggestion="开头承接上章正在进行的动作",
                    )
                )

        if prev_tail and not first_chapter:
            tail = prev_tail[-self.tail_lookback:]
            hard_states = []
            for name, pattern in [
                ("伤势", HARD_INJURY_RE),
                ("被困", HARD_TRAPPED_RE),
                ("关键物品", HARD_CRITICAL_ITEM_RE),
                ("生死危机", HARD_LIFE_DEATH_RE),
            ]:
                matches = pattern.findall(tail)
                if matches:
                    hard_states.append((name, list(set(matches))))

            forgotten = []
            carried = 0
            for name, markers in hard_states:
                if any(marker in content_start for marker in markers):
                    carried += 1
                else:
                    forgotten.append(f"{name}: {', '.join(markers[:3])}")

            bridge_score += min(4, carried * 2)
            if forgotten and carried == 0:
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"硬状态中断: {len(forgotten)}类状态未继承",
                        evidence="; ".join(forgotten[:2]),
                        suggestion="硬伤/被困/关键物品状态应在新章节开头被提及或解释",
                    )
                )

        hooks = prev_brief.get("next_chapter_hooks", []) or prev_hooks
        if isinstance(hooks, str):
            hooks = [hooks]
        if hooks and not first_chapter:
            hook_keywords = set()
            for hook in hooks:
                hook_keywords.update(re.findall(r"[\u4e00-\u9fff]{2,4}", hook))
            matched_hooks = [kw for kw in hook_keywords if kw in content_start]
            bridge_score += min(3, len(matched_hooks))
            if not matched_hooks and hook_keywords:
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"上章{len(hooks)}条钩子未承接",
                        evidence=f"钩子关键词: {', '.join(list(hook_keywords)[:6])}",
                        suggestion="在本章前800字内承接至少1条上章钩子",
                    )
                )

        if not first_chapter:
            vacuum_issues = []
            if prev_tail and not any(word in content_head for word in VACUUM_TRANSITION_WORDS):
                vacuum_issues.append("缺少过渡词")

            sudden_chars = SUDDEN_CHAR_PATTERN.findall(content_head)
            if sudden_chars and not any(word in content_head for word in ["只见", "忽然", "突然", "这时", "正当"]):
                vacuum_issues.append(f"人物突现: {', '.join(sudden_chars[:2])}")

            if vacuum_issues:
                findings.append(
                    self._make_finding(
                        "WARN",
                        "疑似真空续写",
                        evidence="; ".join(vacuum_issues[:3]),
                        suggestion="增加过渡段落或场景桥接",
                    )
                )
            else:
                bridge_score += 2

        if first_chapter:
            return self._component_result(0, "PASS", [])
        if bridge_score >= 8:
            return self._component_result(max(0, 100 - bridge_score * 10), "PASS", findings)
        if bridge_score >= self.min_bridge_score:
            return self._component_result(max(0, 100 - bridge_score * 12), "WARNING", findings)
        return self._component_result(max(60, 100 - bridge_score * 8), "WARNING", findings)

    def _review_continuity(self, content: str, chapter_no: int, context: dict) -> dict:
        prev_tail = context.get("prev_tail", "")
        first_chapter = chapter_no <= 1
        findings = []
        issues_count = 0
        content_start = content[:1000]

        if first_chapter:
            return self._component_result(0, "PASS", [])

        if prev_tail:
            tail = prev_tail[-500:]
            for state_name, pattern in CHAR_STATE_MARKERS.items():
                prev_matches = pattern.findall(tail)
                if not prev_matches:
                    continue
                curr_matches = pattern.findall(content_start)
                if not curr_matches:
                    findings.append(
                        self._make_finding(
                            "WARN",
                            f"人物状态中断: {state_name}",
                            evidence=f"上章出现: {', '.join(list(set(prev_matches))[:3])}",
                            suggestion=f"确保{state_name}状态在本章开头被提及或说明变化",
                        )
                    )
                    issues_count += 1

        if prev_tail:
            tail = prev_tail[-800:]
            prev_items = [item for item in KEY_ITEMS if item in tail]
            for item in prev_items:
                if item not in content and item in ["止血丹", "令牌", "玉简", "法器", "信物", "残片"]:
                    findings.append(
                        self._make_finding(
                            "WARN",
                            f"关键物品失踪: '{item}'",
                            evidence="上章结尾出现，本章全文未见",
                            suggestion=f"说明'{item}'的去向或在本章中出现",
                        )
                    )
                    issues_count += 1

        if prev_tail:
            tail_end = prev_tail[-300:]
            prev_locations = list(set(keyword for keyword in LOCATION_KEYWORDS if keyword in tail_end))
            curr_locations = list(set(keyword for keyword in LOCATION_KEYWORDS if keyword in content_start))
            if prev_locations and curr_locations and not (set(prev_locations) & set(curr_locations)):
                has_transition = any(
                    word in content_start
                    for word in ["离开", "走到", "来到", "回到", "踏入", "进入", "穿过", "翻过", "越过", "经过"]
                )
                if not has_transition:
                    findings.append(
                        self._make_finding(
                            "WARN",
                            "地点跳跃无过渡",
                            evidence=f"上章: {prev_locations}, 本章: {curr_locations}",
                            suggestion="增加转场描写: 离开 -> 路途 -> 到达",
                        )
                    )
                    issues_count += 1

        task_continuity = context.get("task_continuity", "")
        if task_continuity and task_continuity not in content[:1500]:
            findings.append(
                self._make_finding(
                    "WARN",
                    "任务线中断",
                    evidence=f"任务'{task_continuity[:60]}'在本章前半未见",
                    suggestion="在章节前部提及或推进进行中的任务",
                )
            )

        has_night = any(marker in prev_tail[-300:] for marker in ["夜里", "夜晚", "深夜", "半夜", "夜幕"]) if prev_tail else False
        has_day = any(marker in content_start[:300] for marker in ["清晨", "天亮", "早晨", "上午", "中午", "午后", "下午"])
        if has_night and has_day and not TIME_PASSAGE.search(content_start[:200]):
            findings.append(
                self._make_finding(
                    "WARN",
                    "时间跳转无标记: 上章夜晚 -> 本章清晨",
                    suggestion="添加'一夜过去'/'次日清晨'等时间过渡",
                )
            )
            issues_count += 1

        if issues_count == 0:
            return self._component_result(0, "PASS", findings)
        if issues_count <= 2:
            return self._component_result(30 + issues_count * 10, "WARNING", findings)
        return self._component_result(50 + issues_count * 10, "WARNING", findings)
