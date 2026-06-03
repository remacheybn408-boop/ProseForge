#!/usr/bin/env python3
"""
context_agent.py — 上下文承接Agent v0.5.5

检查:
  1. 承接上一章结尾 — 动作/情绪/状态是否延续
  2. 伤势延续 — 硬伤(HARD状态)是否被遗忘
  3. 伏笔/钩子 — 上一章钩子是否在本章前部出现
  4. 真空续写 — 是否有明显"断开重写"痕迹 (场景/人名/时间突变)

策略: 正则+关键词匹配, 不调用外部LLM
"""

import re
from .base_agent import BaseAgent

# ── 伤势/硬状态关键词 (继承自 continuity_evidence_guard) ──
HARD_INJURY_RE = re.compile(
    r'(伤口|流血|骨折|肿|青紫|绷带|包扎|敷药|治疗|养伤|伤势|断臂|残废|濒死|晕倒|眩晕|头晕|昏迷|中毒|血痂|渗血|破皮)')
HARD_TRAPPED_RE = re.compile(r'(被困|锁住|封住|困在|困入|禁锢|无法离开)')
HARD_CRITICAL_ITEM_RE = re.compile(
    r'(止血丸|玉简|令牌|法器|关键丹药|关键证物|证物|残片|密钥|卷轴|禁制符|传送符|信物)')
HARD_LIFE_DEATH_RE = re.compile(r'(死亡|濒死|追杀|生死危机|处刑|审判|毙命|绝境|垂死|将死)')

# ── 真空续写检测 ──
# 主角突然出现在完全不同的场景且无过渡词
VACUUM_TRANSITION_WORDS = {'回到', '来到', '走入', '踏入', '走进', '走到', '经过', '一路', '穿过',
                           '翻过', '顺着', '沿着', '赶路', '出发', '离开', '转场'}
# 时间跳跃过大但无"三日后"/"次日"等标记
TIME_JUMP_MARKERS = {'次日', '第二天', '翌日', '明日', '今天', '今日', '当晚', '当夜', '第二日',
                     '半月后', '一个月后', '三月后', '半年后', '数日之后', '几天后'}
# 突然出现的新人物无引入
SUDDEN_CHAR_PATTERN = re.compile(
    r'(一个.{0,4}(?:人|者|弟子|师兄|师姐|长老|执事|掌柜|老者|少年|女子|男子|修士|散修)(?:走|站|坐|出现|拦|挡|叫|喊|说|问|道))')


class ContextAgent(BaseAgent):
    """上下文承接审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="context_agent", config=config)
        self.min_bridge_score = self.config.get("min_bridge_score", 4)
        self.tail_lookback = self.config.get("tail_lookback", 400)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        context = context or {}
        prev_tail = context.get("prev_tail", "")
        prev_hooks = context.get("prev_hooks", [])
        prev_brief = context.get("prev_brief", {})
        first_chapter = (chapter_no <= 1)

        findings = []
        bridge_score = 0
        max_bridge = 12

        content_start = content[:1200]
        content_head = content[:600]

        # ── 1. 动作承接 (0-3 pts) ──
        if prev_tail and not first_chapter:
            tail = prev_tail[-self.tail_lookback:] if len(prev_tail) > self.tail_lookback else prev_tail
            action_kws = set(re.findall(
                r'(劈|砍|推|搬|拉|抬|抓|按|压|砸|走|跑|站|坐|躺|蹲|'
                r'说|问|答|叫|喊|笑|哭|看|盯|望|指|画|磨|擦|洗|煮|烧|'
                r'考核|验收|登记)', tail))
            matched = [kw for kw in action_kws if kw in content_head]
            bridge_score += min(3, len(matched))
            if len(matched) == 0:
                findings.append(self._make_finding(
                    "WARN", "上一章动作未延续",
                    evidence=f"上章结尾关键词: {', '.join(list(action_kws)[:8])}",
                    suggestion="开头承接上章正在进行的动作"))

        # ── 2. 硬状态继承 (0-4 pts) ──
        if prev_tail and not first_chapter:
            tail = prev_tail[-self.tail_lookback:]
            hard_states = []
            for name, pat in [("伤势", HARD_INJURY_RE), ("被困", HARD_TRAPPED_RE),
                              ("关键物品", HARD_CRITICAL_ITEM_RE), ("生死危机", HARD_LIFE_DEATH_RE)]:
                matches = pat.findall(tail)
                if matches:
                    hard_states.append((name, list(set(matches))))

            forgotten = []
            carried = 0
            for name, markers in hard_states:
                found_any = any(m in content_start for m in markers)
                if found_any:
                    carried += 1
                else:
                    forgotten.append(f"{name}: {', '.join(markers[:3])}")

            bridge_score += min(4, carried * 2)
            if forgotten and carried == 0:
                findings.append(self._make_finding(
                    "WARN", f"硬状态中断: {len(forgotten)}类状态未继承",
                    evidence="; ".join(forgotten[:2]),
                    suggestion="硬伤/被困/关键物品状态必须在新章节开头出现"))

        # ── 3. 钩子承接 (0-3 pts) ──
        hooks = prev_brief.get("next_chapter_hooks", []) or prev_hooks
        if isinstance(hooks, str):
            hooks = [hooks]
        if hooks and not first_chapter:
            hook_keywords = set()
            for hook in hooks:
                hook_keywords.update(re.findall(r'[\u4e00-\u9fff]{2,4}', hook))
            matched_hooks = [kw for kw in hook_keywords if kw in content_start]
            bridge_score += min(3, len(matched_hooks))
            if len(matched_hooks) == 0:
                findings.append(self._make_finding(
                    "WARN", f"上章{len(hooks)}条钩子未承接",
                    evidence=f"钩子关键词: {', '.join(list(hook_keywords)[:6])}",
                    suggestion="在本章前800字内承接至少1条上章钩子"))

        # ── 4. 真空续写检测 (0-2 pts) ──
        if not first_chapter:
            vacuum_issues = []
            # 检查过渡
            if prev_tail and not any(w in content_head for w in VACUUM_TRANSITION_WORDS):
                vacuum_issues.append("缺少过渡词")

            # 检查时间跳跃
            if not any(w in content_start for w in TIME_JUMP_MARKERS):
                # Not a problem per se, but note it
                pass

            # 检查突然新人物
            sudden_chars = SUDDEN_CHAR_PATTERN.findall(content_head)
            if sudden_chars and not any(w in content_head for w in ['只见', '忽然', '突然', '这时', '正当']):
                vacuum_issues.append(f"人物突现: {', '.join(sudden_chars[:2])}")

            if vacuum_issues:
                findings.append(self._make_finding(
                    "WARN", "疑似真空续写",
                    evidence="; ".join(vacuum_issues[:3]),
                    suggestion="增加过渡段落或场景桥接"))
            else:
                bridge_score += 2

        # ── 裁决 ──
        if first_chapter:
            score = 0
            status = "PASS"
        elif bridge_score >= 8:
            score = max(0, 100 - bridge_score * 10)
            status = "PASS"
        elif bridge_score >= self.min_bridge_score:
            score = max(0, 100 - bridge_score * 12)
            status = "WARNING"
        else:
            score = max(60, 100 - bridge_score * 8)
            status = "WARNING"

        # 有硬状态遗忘则至少 WARNING
        has_hard_forgotten = any("硬状态中断" in f["message"] for f in findings)
        if has_hard_forgotten and status == "PASS":
            status = "WARNING"
            score = max(score, 50)

        return self._build_result(score, status, findings)
