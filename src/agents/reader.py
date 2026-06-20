#!/usr/bin/env python3
"""Merged reader agent."""

import re

from .base_agent import BaseAgent


HOOK_MARKERS = [
    re.compile(r"(突然|忽然|猛然|骤然)"),
    re.compile(r"(但|然而|不过|没想到|出乎意料)"),
    re.compile(r"[？?]"),
    re.compile(r"(发现|察觉|看到|注意到)"),
    re.compile(r"(是谁|什么|为什么|怎么|如何)"),
    re.compile(r"(冷笑|神秘|诡异|不寻常|奇怪|异样)"),
]
MICRO_PAYOFF_MARKERS = [
    re.compile(r"(原来如此|果然|难怪)"),
    re.compile(r"(不出所料|果然如此)"),
    re.compile(r"(终于|总算|到头来)"),
    re.compile(r"(收获|得到|获得|成功|突破)"),
    re.compile(r"(揭开|显露|露出|显现|现身)"),
]
READER_PULL_MARKERS = [
    (re.compile(r"(危险|危机|凶险|陷阱|杀机|必死)"), "危机驱动"),
    (re.compile(r"(秘密|真相|谜|答案|[？?])"), "谜题驱动"),
    (re.compile(r"(冷笑$|不见$|消失$|突然$|.*不好$|糟了$)"), "悬念驱动"),
    (re.compile(r"(走去|出发|前进|跟上|进去|冲入)"), "行动驱动"),
    (re.compile(r"(突破|升级|变强|质变|蜕变)"), "成长驱动"),
    (re.compile(r"(等你|我在.*等你|来找我|别让我失望)"), "人物驱动"),
]
OPENING_HOOK_PATTERNS = [
    re.compile(r"^.{0,50}(?:突然|忽然|猛然|骤然)"),
    re.compile(r"^.{0,50}(?:但|然而|不过)"),
    re.compile(r"^.{0,50}[？?]"),
    re.compile(r"^.{0,50}(?:冷笑|惨叫|爆炸|碎裂|裂开)"),
    re.compile(r"^.{0,50}(?:不好|糟了|完了|死)"),
]
WEAK_OPENING_PATTERNS = [
    re.compile(r"^.{0,40}(?:早晨|早上|清早|天亮了|清晨)"),
    re.compile(r"^.{0,40}(?:走了过去|来到)"),
    re.compile(r"^.{0,40}(?:在|站在|坐在|躺在)"),
]
EMOTION_BURSTS = [
    re.compile(r"(暴怒|大怒|狂怒|愤怒至极|怒不可遏|勃然大怒)"),
    re.compile(r"(崩溃|垮掉|决堤|失控|失声|嚎啕)"),
    re.compile(r"(感动|哭泣|泪流|红了眼眶|鼻子一酸)"),
    re.compile(r"(顿悟|豁然|恍然|醒悟|一下子明白)"),
]
EMOTION_BUILDUP = [
    re.compile(r"(隐隐|渐渐|慢慢|逐渐|一点点|越来越)"),
    re.compile(r"(压下|强忍|憋着|按住|攥紧拳头|咬着牙)"),
    re.compile(r"(不安|不对|不好|不妙|不对劲)"),
    re.compile(r"(深吸|呼出|吐了口气|缓了缓)"),
]
EMOTION_LABELS = [
    re.compile(r"(很(高兴|难过|震惊|生气|失望|感动|害怕|紧张|焦虑|兴奋|激动))"),
    re.compile(r"(非常(高兴|难过|震惊|生气|失望|感动|害怕|紧张|焦虑|兴奋|激动))"),
    re.compile(r"(极度(高兴|难过|震惊|生气|失望|感动|害怕|紧张|焦虑|兴奋|激动))"),
]


class ReaderAgent(BaseAgent):
    """Merged reader pull/emotion curve agent."""

    def __init__(self, config: dict = None):
        super().__init__(name="reader_agent", config=config)
        self.min_hooks = self.config.get("min_hooks", 3)
        self.min_payoffs = self.config.get("min_payoffs", 0)
        self.tail_chars = self.config.get("tail_chars", 500)
        self.min_buildup_per_burst = self.config.get("min_buildup_per_burst", 1)

    def review(self, content: str, chapter_no: int = 0, context: dict = None) -> dict:
        components = [
            self._review_reader_pull(content, chapter_no),
            self._review_emotion_curve(content),
        ]
        return self._merge_components(components)

    def _review_reader_pull(self, content: str, chapter_no: int) -> dict:
        findings = []
        score = 0
        paragraphs = self._get_paragraphs(content)
        if not paragraphs:
            return self._component_result(100, "FAIL", [self._make_finding("FAIL", "空章节")])

        hook_count = 0
        hook_sections = {"opening": 0, "middle": 0, "ending": 0}
        total_chars = len(content)
        third = total_chars // 3
        for pattern in HOOK_MARKERS:
            for match in pattern.finditer(content):
                pos = match.start()
                hook_count += 1
                if pos < third:
                    hook_sections["opening"] += 1
                elif pos < third * 2:
                    hook_sections["middle"] += 1
                else:
                    hook_sections["ending"] += 1

        if hook_count < self.min_hooks:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"钩子密度偏低: 少于{self.min_hooks}个悬念标记",
                    suggestion="增加转折、问题或突发事件，每章至少3个",
                )
            )
            score += 20

        if hook_sections["ending"] == 0:
            findings.append(
                self._make_finding(
                    "WARN",
                    "结尾无钩子: 追读驱动力不足",
                    suggestion="结尾设置疑问、转折、危机或行动指令",
                )
            )
            score += 25

        payoff_count = sum(len(pattern.findall(content)) for pattern in MICRO_PAYOFF_MARKERS)
        if payoff_count == 0 and chapter_no > 1:
            findings.append(
                self._make_finding(
                    "WARN",
                    "无微兑现: 读者等待的回报未出现",
                    evidence="本章没有'果然/终于/原来如此'等回报信号",
                    suggestion="至少给读者一个小满足点: 揭秘、收获或确认",
                )
            )
            score += 10

        new_question_pattern = re.compile(r"(但|然而|不过).{0,30}(新|又|再|还).*?(问题|疑问|麻烦)")
        if len(new_question_pattern.findall(content)) == 0 and chapter_no > 1:
            findings.append(
                self._make_finding(
                    "WARN",
                    "未抛出新问题",
                    suggestion="在解决旧矛盾的同时引入新问题，保持故事持续驱动",
                )
            )

        tail = content[-self.tail_chars:] if len(content) > self.tail_chars else content
        tail_paragraphs = self._get_paragraphs(tail)
        ending_text = "\n".join(tail_paragraphs[-3:]) if tail_paragraphs else tail
        pull_types = [pull_type for pattern, pull_type in READER_PULL_MARKERS if pattern.search(ending_text)]
        if not pull_types:
            findings.append(
                self._make_finding(
                    "WARN",
                    "结尾追读力弱: 无悬念、危机、谜题或行动驱动",
                    evidence=f"结尾3段: {ending_text[:100]}...",
                    suggestion="结尾必须是钩子: 危机逼近、谜面抛出、行动启动或反转",
                )
            )
            score += 30

        first_paragraph = paragraphs[0]
        opening_hooked = any(pattern.search(first_paragraph) for pattern in OPENING_HOOK_PATTERNS)
        opening_weak = any(pattern.search(first_paragraph) for pattern in WEAK_OPENING_PATTERNS)
        if opening_weak and not opening_hooked:
            findings.append(
                self._make_finding(
                    "WARN",
                    "开篇平淡: 缺少悬念、动作或冲突",
                    evidence=first_paragraph[:80],
                    suggestion="开头50字内应尽量有冲突、悬念、动作或强对白",
                )
            )
            score += 15
        elif opening_hooked:
            score = max(0, score - 5)

        score = max(0, min(100, score))
        status = "PASS" if score == 0 else ("WARNING" if score <= 40 else "FAIL")
        return self._component_result(score, status, findings)

    def _review_emotion_curve(self, content: str) -> dict:
        findings = []
        score = 60

        burst_count = 0
        burst_samples = []
        for pattern in EMOTION_BURSTS:
            matches = pattern.findall(content)
            burst_count += len(matches)
            if matches:
                burst_samples.append(matches[0][:40])

        buildup_count = sum(len(pattern.findall(content)) for pattern in EMOTION_BUILDUP)

        label_count = 0
        label_samples = []
        for pattern in EMOTION_LABELS:
            matches = pattern.findall(content)
            label_count += len(matches)
            if matches:
                label_samples.append(str(matches[0])[:40])

        if label_count >= 3:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"情绪标签过多({label_count}处): 只贴标签不写过程",
                    evidence=str(label_samples[:3]),
                    suggestion="少写'很震惊/非常感动'，多用身体反应和动作表现情绪",
                )
            )
            score -= 20

        if burst_count > 0 and buildup_count < burst_count * self.min_buildup_per_burst:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"情绪跳跃: {burst_count}处爆发，仅{buildup_count}处铺垫",
                    evidence=str(burst_samples[:3]),
                    suggestion="情绪爆发前应有不安、压抑或犹豫等过渡层",
                )
            )
            score -= 15
        elif buildup_count >= 6:
            score += 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)
