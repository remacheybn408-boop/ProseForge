#!/usr/bin/env python3
"""
voice_agent.py — 角色口吻/语体Agent v0.5.5

检查:
  1. 角色口吻一致性 — 某角色是否说了不符合其设定的台词
  2. 方言浓度 — 方言词是否过多/过少
  3. 梗/语言包 — 网络梗检测、禁用梗
  4. 英语/现代词污染 — 旁白或对白是否混入不恰当现代词
  5. 角色声纹缺失 — 角色有对话但无个性特征

策略: 基于 voice_packs 配置文件做启发式匹配
"""

import re
from .base_agent import BaseAgent

# ── 对白提取 ──
LQ = "\u201c"  # "
RQ = "\u201d"  # "
LJ = "\u300c"  # 「
RJ = "\u300d"  # 」
DIALOGUE_PATTERN = re.compile(
    f"[{LQ}{RQ}{LJ}{RJ}]([^{LQ}{RQ}{LJ}{RJ}]{{5,200}})[{LQ}{RQ}{LJ}{RJ}]")
SPEAKER_PATTERN = re.compile(
    r'([^\s，。！？]{1,6}?)[说问道喊叫吼骂叹曰：:]')

# ── AI腔/模板句 (旁白) ──
NARRATION_AI_PATTERNS = [
    (re.compile(r'(不由得|不禁|忍不住|不由自主)'), "旁白主观"),  # already has 不由得
    (re.compile(r'(仿佛|似乎)在说'), "拟人旁白"),
    (re.compile(r'像是.{1,20}(一般|似的|一样)'), "比喻泛滥"),
]

# ── 网络梗 (不检测对白中的, 仅旁白) ──
NET_MEME_PATTERNS = [
    (re.compile(r'(我了个去|卧槽|尼玛|牛逼|傻逼|特么)'), "粗俗网络梗"),
    (re.compile(r'(社死|破防|上头|下头|芭比Q|完了芭比Q)'), "轻网络梗"),
    (re.compile(r'(绝绝子|YYDS|栓Q|刺客|刺客流|刺客党)'), "潮流梗"),
]

# ── 英语/罗马字 ──
ENGLISH_WORD_RE = re.compile(r'\b[a-zA-Z]{2,20}\b')
ALLOWED_ENGLISH = {'A', 'B', 'C', 'D', 'a', 'an', 'the', 'OK', 'ok'}

# ── 角色声纹标记 (通用) ──
VOICE_SIGNATURE_WORDS = {
    '冷峻': {'哼', '也罢', '不自量力', '聒噪', '找死'},
    '粗犷': {'娘的', '奶奶的', '老子', '爽快', '干'},
    '儒雅': {'请', '阁下', '不敢', '承让', '惭愧'},
    '暴躁': {'滚', '混账', '放肆', '该死', '岂有此理'},
    '阴险': {'呵呵', '很好', '有意思', '不急', '慢慢来'},
}


class VoiceAgent(BaseAgent):
    """角色口吻审查 Agent"""

    def __init__(self, config: dict = None):
        super().__init__(name="voice_agent", config=config)
        self.max_narration_ai = self.config.get("max_narration_ai", 2)
        self.max_memes = self.config.get("max_memes", 1)
        self.max_english = self.config.get("max_english", 2)

    def review(self, content: str, chapter_no: int = 0,
               context: dict = None) -> dict:
        context = context or {}
        voice_profiles = context.get("voice_profiles", [])
        voice_packs = context.get("voice_packs", {})

        findings = []
        issues_weight = 0  # 0-100

        # ── 1. 提取对白/旁白 ──
        dialogues = []
        for m in DIALOGUE_PATTERN.finditer(content):
            text = m.group(1)
            start = max(0, m.start() - 30)
            ctx = content[start:m.start()]
            sp_match = SPEAKER_PATTERN.search(ctx)
            speaker = sp_match.group(1) if sp_match else "未知"
            dialogues.append({"text": text, "speaker": speaker})

        narration = re.sub(
            f"[{LQ}{RQ}{LJ}{RJ}][^{LQ}{RQ}{LJ}{RJ}]+[{LQ}{RQ}{LJ}{RJ}]",
            '', content)

        # ── 2. 旁白AI腔检测 ──
        narration_ai_count = 0
        for pat, label in NARRATION_AI_PATTERNS:
            matches = pat.findall(narration)
            if matches:
                narration_ai_count += len(matches)
                if len(matches) >= 2:
                    findings.append(self._make_finding(
                        "WARN", f"旁白{label}: 出现{len(matches)}次",
                        evidence=matches[0][:50] if isinstance(matches[0], str) else str(matches[:2]),
                        suggestion="旁白应客观冷静, 避免主观感叹词"))
        issues_weight += min(30, narration_ai_count * 8)

        # ── 3. 旁白网络梗检测 ──
        for pat, label in NET_MEME_PATTERNS:
            matches = pat.findall(narration)
            if matches:
                findings.append(self._make_finding(
                    "WARN", f"旁白含网络梗 ({label}): {', '.join(matches[:3])}",
                    evidence=str(matches[:3]),
                    suggestion=f"旁白禁止使用网络梗, 对白中可酌情使用"))
                issues_weight += 15

        # ── 4. 英语/罗马字检测 ──
        eng_words = [w for w in ENGLISH_WORD_RE.findall(content)
                     if w not in ALLOWED_ENGLISH]
        if len(eng_words) > self.max_english:
            findings.append(self._make_finding(
                "WARN", f"英文/罗马字过多: {len(eng_words)}个",
                evidence=', '.join(eng_words[:8]),
                suggestion=f"修仙文中英文不宜超过{self.max_english}个/章"))
            issues_weight += len(eng_words) * 5

        # ── 5. 角色声纹检测 ──
        speaker_counts = {}
        speaker_texts = {}
        for d in dialogues:
            s = d["speaker"]
            speaker_counts[s] = speaker_counts.get(s, 0) + 1
            speaker_texts[s] = (speaker_texts.get(s, "") + " " + d["text"])

        # 检查有对话但无声纹特征的角色
        for speaker, count in speaker_counts.items():
            if count < 2:
                continue
            combined = speaker_texts.get(speaker, "")
            has_signature = False
            for style, words in VOICE_SIGNATURE_WORDS.items():
                if any(w in combined for w in words):
                    has_signature = True
                    break
            if not has_signature and count >= 4 and len(combined) > 80:
                findings.append(self._make_finding(
                    "WARN", f"角色'{speaker}'对话{count}次但无声纹特征",
                    evidence=f"对白量: {len(combined)}字",
                    suggestion=f"为'{speaker}'添加标志性口头禅或句式"))
                issues_weight += 10

        # ── 6. 方言浓度 (如果有 packs) ──
        if voice_packs:
            dialect_packs = {
                pid: pack for pid, pack in voice_packs.items()
                if pack.get("type") == "dialect"
            }
            for pid, pack in dialect_packs.items():
                markers = pack.get("markers", [])
                hits = [m for m in markers if m in content]
                if len(hits) > pack.get("overuse_warning_threshold", 8):
                    findings.append(self._make_finding(
                        "WARN", f"方言'{pid}'浓度过高: {len(hits)}次",
                        evidence=', '.join(hits[:6]),
                        suggestion=f"每章方言标记建议≤{pack.get('overuse_warning_threshold', 8)}次"))
                    issues_weight += 10
                if pack.get("soft_markers"):
                    soft = [m for m in pack["soft_markers"] if m in content]
                    if len(soft) > pack.get("overuse_warning_threshold", 8):
                        findings.append(self._make_finding(
                            "WARN", f"方言'{pid}'软标记过多: {len(soft)}次",
                            evidence=', '.join(soft[:6]),
                            suggestion="软方言标记也应控制频率"))

        # ── 裁决 ──
        score = min(100, issues_weight)
        if issues_weight == 0:
            status = "PASS"
        elif issues_weight <= 25:
            status = "WARNING"
        else:
            status = "WARNING"

        return self._build_result(score, status, findings)
