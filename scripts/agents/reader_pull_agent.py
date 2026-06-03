#!/usr/bin/env python3
"""
reader_pull_agent.py — 读者追读力Agent v0.5.5

检查:
  1. 钩子密度 — 每章的悬念/问题/转折分布
  2. 微兑现 — 读者预期是否得到部分回报
  3. 新问题 — 是否在解决旧问题的同时抛出新问题
  4. 追读力 — 结尾驱动力评估 (读者是否想点下一章)
  5. 开篇抓人 — 开头第一段是否值得继续读

策略: 结构分析 + 关键词, 重点看开头/结尾
"""

import re
from .base_agent import BaseAgent

# ── 钩子/悬念标记 ──
HOOK_MARKERS = [
    re.compile(r'(突然|忽然|猛然|骤然)'),  # 突发事件
    re.compile(r'(却|但|然而|可|不过|没想到|出乎意料)'),  # 转折
    re.compile(r'[？?]'),  # 疑问
    re.compile(r'(发现|察觉|看到|注意到)'),  # 新发现
    re.compile(r'(是谁|什么|为什么|怎么|如何)'),  # 疑问词
    re.compile(r'(冷笑|神秘|诡异|不寻常|奇怪|异样)'),  # 氛围悬念
]

# ── 微兑现标记 ──
MICRO_PAYOFF_MARKERS = [
    re.compile(r'(原来如此|果然|难怪|怪不得)'),  # 谜题揭晓
    re.compile(r'(果然|不出所料|果然如此)'),  # 预期兑现
    re.compile(r'(终于|总算|到头来)'),  # 等待后兑现
    re.compile(r'(收获|得到|获得|成功|突破)'),  # 回报
    re.compile(r'(揭开|显露|露出|显现|现身)'),  # 隐藏揭示
]

# ── 追读力标记 (结尾分析) ──
READER_PULL_MARKERS = [
    (re.compile(r'(危险|危机|凶险|陷阱|杀机|必死)'), "危机驱动"),
    (re.compile(r'(秘密|真相|谜|答案|[？?])'), "谜题驱动"),
    (re.compile(r'(冷笑$|不见$|消失$|突然$|.*不好$|糟了$)'), "悬念驱动"),
    (re.compile(r'(走|去|出发|前进|跟上|追|冲)'), "行动驱动"),
    (re.compile(r'(突破|升级|变强|质变|蜕变)'), "成长驱动"),
    (re.compile(r'(等你|我在.*等你|来找我|别让我失望)'), "人物驱动"),
]

# ── 开篇抓人标记 ──
OPENING_HOOK_PATTERNS = [
    re.compile(r'^.{0,50}(?:突然|忽然|猛然|骤然)'),
    re.compile(r'^.{0,50}(?:却|但|然而|可)'),
    re.compile(r'^.{0,50}[？?]'),
    re.compile(r'^.{0,50}(?:冷笑|惨叫|爆炸|碎裂|裂开)'),
    re.compile(r'^.{0,50}(?:不好|糟了|完了|死)'),
]

# ── 弱开篇模式 ──
WEAK_OPENING_PATTERNS = [
    re.compile(r'^.{0,40}(?:早晨|早上|清早|天亮了|清晨)'),
    re.compile(r'^.{0,40}(?:走|来|去|到)'),  # 以平淡动作起头
    re.compile(r'^.{0,40}(?:在|站在|坐在|躺在)'),  # 静态描写
]


class ReaderPullAgent(BaseAgent):
    """读者追读力审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="reader_pull_agent", config=config)
        self.min_hooks = self.config.get("min_hooks", 3)
        self.min_payoffs = self.config.get("min_payoffs", 0)  # 不强求
        self.tail_chars = self.config.get("tail_chars", 500)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        findings = []
        score = 0  # 0 = perfect, accumulates issues

        paragraphs = self._get_paragraphs(content)
        if not paragraphs:
            return self._build_result(100, "FAIL",
                                       [self._make_finding("FAIL", "空章节")])

        # ── 1. 钩子密度 ──
        hook_count = 0
        hook_sections = {"开头": 0, "中段": 0, "结尾": 0}
        total_chars = len(content)
        third = total_chars // 3

        for pat in HOOK_MARKERS:
            for m in pat.finditer(content):
                pos = m.start()
                hook_count += 1
                if pos < third:
                    hook_sections["开头"] += 1
                elif pos < third * 2:
                    hook_sections["中段"] += 1
                else:
                    hook_sections["结尾"] += 1

        if hook_count < self.min_hooks:
            findings.append(self._make_finding(
                "WARN", f"钩子密度过低: 仅{self.min_hooks}个悬念标记",
                suggestion="增加转折/疑问/突发事件, 每章至少3个"))
            score += 20

        # 检查分布: 结尾是否有钩子
        if hook_sections["结尾"] == 0:
            findings.append(self._make_finding(
                "WARN", "结尾无钩子: 读者缺乏点击下一章的动力",
                suggestion="结尾设置疑问/转折/危机/行动指令"))
            score += 25

        # ── 2. 微兑现 ──
        payoff_count = 0
        for pat in MICRO_PAYOFF_MARKERS:
            payoff_count += len(pat.findall(content))

        # 不强求, 但完全无兑现会扣分
        if payoff_count == 0 and chapter_no > 1:
            findings.append(self._make_finding(
                "WARN", "无微兑现: 读者等待的回报未出现",
                evidence="本章无'原来如此/果然/终于'等兑现标记",
                suggestion="至少给读者一个小的满足点: 揭秘/收获/确认"))
            score += 10

        # ── 3. 新问题 ──
        new_question_pattern = re.compile(
            r'(但|却|然而|可|不过).{0,30}(新|又|再|还|仍)')
        new_questions = new_question_pattern.findall(content)
        if len(new_questions) == 0 and chapter_no > 1:
            findings.append(self._make_finding(
                "WARN", "未抛出新问题",
                suggestion="在解决旧矛盾的同时引入新矛盾, 保持故事持续驱动"))

        # ── 4. 结尾追读力分析 ──
        tail = content[-self.tail_chars:] if len(content) > self.tail_chars else content
        tail_paragraphs = self._get_paragraphs(tail)
        ending_text = '\n'.join(tail_paragraphs[-3:]) if tail_paragraphs else tail

        pull_types = []
        for pat, pull_type in READER_PULL_MARKERS:
            if pat.search(ending_text):
                pull_types.append(pull_type)

        if not pull_types:
            findings.append(self._make_finding(
                "WARN", "结尾追读力弱: 无悬念/危机/谜题/行动驱动",
                evidence=f"结尾3段: {ending_text[:100]}...",
                suggestion="结尾必须是钩子: 危机逼近/谜题抛出/行动启动/反转"))
            score += 30
        else:
            # 记录追读类型
            pass

        # ── 5. 开篇抓人 ──
        first_paragraph = paragraphs[0] if paragraphs else ""
        opening_hooked = any(pat.search(first_paragraph) for pat in OPENING_HOOK_PATTERNS)
        opening_weak = any(pat.search(first_paragraph) for pat in WEAK_OPENING_PATTERNS)

        if opening_weak and not opening_hooked:
            findings.append(self._make_finding(
                "WARN", "开篇平淡: 无悬念/动作/冲突",
                evidence=first_paragraph[:80],
                suggestion="开头30字内必须抓人: 冲突/悬念/动作/对话"))
            score += 15
        elif opening_hooked:
            score -= 5  # bonus

        # ── 裁决 ──
        score = max(0, min(100, score))

        if score == 0:
            status = "PASS"
        elif score <= 40:
            status = "WARNING"
        else:
            status = "FAIL"

        return self._build_result(score, status, findings)
