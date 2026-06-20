#!/usr/bin/env python3
"""Merged character agent."""

import re
from pathlib import Path

from .base_agent import BaseAgent


LQ = "\u201c"
RQ = "\u201d"
LJ = "\u300c"
RJ = "\u300d"
DIALOGUE_PATTERN = re.compile(f"[{LQ}{RQ}{LJ}{RJ}]([^{LQ}{RQ}{LJ}{RJ}]{{5,200}})[{LQ}{RQ}{LJ}{RJ}]")
SPEAKER_PATTERN = re.compile(r"([^\s，。！？\n]{1,6}?)[说问道喊叫吼骂叹笑：:]")
NARRATION_AI_PATTERNS = [
    (re.compile(r"(不由得|不禁|忍不住|不由自主)"), "旁白主观"),
    (re.compile(r"(仿佛|似乎)在说"), "拟人旁白"),
    (re.compile(r"像是.{1,20}(一般|一样)"), "比喻泛化"),
]
NET_MEME_PATTERNS = [
    (re.compile(r"(我了个去|卧槽|尼玛|牛逼|傻逼|特么)"), "粗俗网络梗"),
    (re.compile(r"(社死|破防|上头|下头|芭比Q|完了芭比Q)"), "轻网络梗"),
    (re.compile(r"(绝绝子|YYDS|梗|刺客)"), "潮流梗"),
]
ENGLISH_WORD_RE = re.compile(r"\b[a-zA-Z]{2,20}\b")
ALLOWED_ENGLISH = {"A", "B", "C", "D", "a", "an", "the", "OK", "ok"}
VOICE_SIGNATURE_WORDS = {
    "冷系": {"呵", "也罢", "不自量力", "聒噪", "找死"},
    "粗犷": {"娘的", "奶奶的", "老子", "爽快", "干"},
    "儒雅": {"请", "阁下", "不敢", "承让", "惭愧"},
    "暴躁": {"滚", "混账", "放肆", "该死", "岂有此理"},
    "阴险": {"呵呵", "很好", "有意思", "不急", "慢慢来"},
}

EXTREME_EMOTION_WORDS = {
    "极度": 5, "非常": 3, "无比": 4, "万分": 4, "极其": 4, "绝顶": 4,
    "撕心裂肺": 5, "痛不欲生": 5, "生不如死": 5, "肝肠寸断": 5,
    "欣喜若狂": 4, "暴跳如雷": 4, "怒不可遏": 4, "惊恐万状": 5,
    "毛骨悚然": 4, "魂飞魄散": 5, "肝胆俱裂": 5,
    "微微": 1, "些许": 1, "有点": 1, "有些": 1,
}
PROGRESSIVE_WORDS = [
    "渐渐", "慢慢", "越来越", "日益", "日复一日", "反复",
    "开始", "有些", "有点", "似乎", "仿佛", "隐约",
]
ABRUPT_WORDS = [
    "突然", "忽然", "猛地", "一下子", "毫无征兆",
    "莫名其妙", "不知道为什么", "毫无理由",
]
DIAGNOSTIC_LABELS = [
    "他疯了", "她疯了", "他精神", "她精神", "心理变态",
    "神经病", "精神病", "他有病", "她有病",
]

RELATIONSHIP_CHANGE = [
    re.compile(r"(信任|信赖|相信|放心)"),
    re.compile(r"(怀疑|猜疑|不信|试探|提防|防备)"),
    re.compile(r"(感谢|感激|感恩|感动|欠|恩情|人情)"),
    re.compile(r"(误会|误解|错怪|冤枉|委屈)"),
    re.compile(r"(道歉|认错|赔罪|低头|服软)"),
    re.compile(r"(疏远|冷淡|避开|绕开|不再|陌生)"),
    re.compile(r"(靠拢|接近|拉近|走近|亲近了)"),
    re.compile(r"(利用|算计|坑害|骗|弄死)"),
    re.compile(r"(指点|教导|引导|提携|提拔)"),
    re.compile(r"(承诺|答应|约定|保证|发誓|绝不)"),
]


class CharacterAgent(BaseAgent):
    """Merged character/voice/relationship agent."""

    def __init__(self, config: dict = None):
        super().__init__(name="character_agent", config=config)
        self.max_english = self.config.get("max_english", 2)
        self.min_changes = self.config.get("min_changes", 3)
        self.min_buildup_per_burst = self.config.get("min_buildup_per_burst", 1)

    def review(self, content: str, chapter_no: int = 0, context: dict = None) -> dict:
        context = context or {}
        components = [
            self._review_voice(content, context),
            self._review_psychology(content, context),
            self._review_relationship(content),
        ]
        return self._merge_components(components)

    def _review_voice(self, content: str, context: dict) -> dict:
        voice_packs = context.get("voice_packs", {})
        findings = []
        issues_weight = 0

        dialogues = []
        for match in DIALOGUE_PATTERN.finditer(content):
            text = match.group(1)
            start = max(0, match.start() - 30)
            ctx = content[start:match.start()]
            speaker_match = SPEAKER_PATTERN.search(ctx)
            speaker = speaker_match.group(1) if speaker_match else "未知"
            dialogues.append({"text": text, "speaker": speaker})

        narration = re.sub(f"[{LQ}{RQ}{LJ}{RJ}][^{LQ}{RQ}{LJ}{RJ}]+[{LQ}{RQ}{LJ}{RJ}]", "", content)

        narration_ai_count = 0
        for pattern, label in NARRATION_AI_PATTERNS:
            matches = pattern.findall(narration)
            if matches:
                narration_ai_count += len(matches)
                if len(matches) >= 2:
                    evidence = matches[0][:50] if isinstance(matches[0], str) else str(matches[:2])
                    findings.append(
                        self._make_finding(
                            "WARN",
                            f"旁白{label}: 出现{len(matches)}次",
                            evidence=evidence,
                            suggestion="旁白应客观冷面，避免主观感叹语",
                        )
                    )
        issues_weight += min(30, narration_ai_count * 8)

        for pattern, label in NET_MEME_PATTERNS:
            matches = pattern.findall(narration)
            if matches:
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"旁白含网络梗 ({label}): {', '.join(matches[:3])}",
                        evidence=str(matches[:3]),
                        suggestion="旁白禁止使用网络梗，对白中可酌情使用",
                    )
                )
                issues_weight += 15

        eng_words = [word for word in ENGLISH_WORD_RE.findall(content) if word not in ALLOWED_ENGLISH]
        if len(eng_words) > self.max_english:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"英文/罗马字过多: {len(eng_words)}处",
                    evidence=", ".join(eng_words[:8]),
                    suggestion=f"正文中英文不宜超过{self.max_english}个",
                )
            )
            issues_weight += len(eng_words) * 5

        speaker_counts = {}
        speaker_texts = {}
        for dialogue in dialogues:
            speaker = dialogue["speaker"]
            speaker_counts[speaker] = speaker_counts.get(speaker, 0) + 1
            speaker_texts[speaker] = f"{speaker_texts.get(speaker, '')} {dialogue['text']}"

        for speaker, count in speaker_counts.items():
            if count < 2:
                continue
            combined = speaker_texts.get(speaker, "")
            has_signature = any(any(word in combined for word in words) for words in VOICE_SIGNATURE_WORDS.values())
            if not has_signature and count >= 4 and len(combined) > 80:
                findings.append(
                    self._make_finding(
                        "WARN",
                        f"角色'{speaker}'对话{count}次但无声纹特征",
                        evidence=f"对话量: {len(combined)}字",
                        suggestion=f"为'{speaker}'添加标志性口头禅或句式",
                    )
                )
                issues_weight += 10

        if voice_packs:
            dialect_packs = {
                pack_id: pack for pack_id, pack in voice_packs.items()
                if pack.get("type") == "dialect"
            }
            for pack_id, pack in dialect_packs.items():
                markers = pack.get("markers", [])
                hits = [marker for marker in markers if marker in content]
                if len(hits) > pack.get("overuse_warning_threshold", 8):
                    findings.append(
                        self._make_finding(
                            "WARN",
                            f"方言'{pack_id}'浓度过高: {len(hits)}次",
                            evidence=", ".join(hits[:6]),
                            suggestion=f"每章方言标记建议≤{pack.get('overuse_warning_threshold', 8)}次",
                        )
                    )
                    issues_weight += 10

        status = "PASS" if issues_weight == 0 else "WARNING"
        return self._component_result(min(100, issues_weight), status, findings)

    def _review_psychology(self, content: str, context: dict) -> dict:
        findings = []
        score = 60
        cards = self._load_character_psychologies()
        if not cards:
            return self._component_result(0, "PASS", [])

        for card in cards:
            name = card.get("name", "?")
            psychology = card.get("character_psychology") or card.get("mental_state") or {}
            if not psychology:
                continue

            for category, data in psychology.items():
                if data is None:
                    continue
                severity = data.get("severity", 0)
                if severity == 0:
                    continue

                triggers = data.get("triggers", [])
                manifestations = data.get("manifestations", [])

                if triggers:
                    active_triggers = []
                    for trigger in triggers:
                        trigger_pos = content.find(trigger)
                        if trigger_pos >= 0:
                            active_triggers.append((trigger, trigger_pos))
                    if active_triggers:
                        missing_manifests = []
                        for trigger, pos in active_triggers:
                            window = content[max(0, pos - 100):pos + 300]
                            has_manifest = any(manifestation in window for manifestation in manifestations)
                            if not has_manifest:
                                missing_manifests.append(trigger)
                        if missing_manifests:
                            evidence = content[max(0, active_triggers[0][1] - 50):active_triggers[0][1] + 150]
                            findings.append(
                                self._make_finding(
                                    "WARN",
                                    f"《{name}》的《{category}》触发词《{'/'.join(missing_manifests[:3])}》出现但附近未见对应表现",
                                    evidence=evidence,
                                    suggestion=f"在触发场景附近加入《{name}》的{category}反应描写，如{'/'.join(manifestations[:3]) if manifestations else '颤抖/回避/闪回'}",
                                )
                            )
                            score -= 15

                char_text = self._get_char_text_segments(content, name)
                extreme_score = self._calc_emotion_intensity(char_text)
                expected_score = severity * 10
                deviation = abs(extreme_score - expected_score)
                if deviation > 15:
                    direction = "偏高" if extreme_score > expected_score else "偏低"
                    level = "FAIL" if deviation > 25 else "WARN"
                    score -= 20 if deviation > 25 else 15
                    findings.append(
                        self._make_finding(
                            level,
                            f"《{name}》的《{category}》设定severity={severity}，但本章情绪强度{extreme_score}，{direction}{deviation}分",
                            suggestion="收敛极端用词" if direction == "偏高" else f"增加《{name}》{category}的正面描写以匹配设定",
                        )
                    )

                naturality_score = self._check_naturality(content, severity)
                if naturality_score < 0:
                    findings.append(
                        self._make_finding(
                            "WARN" if naturality_score > -3 else "FAIL",
                            f"《{name}》的《{category}》描写缺乏渐进铺垫" if naturality_score > -3 else f"《{name}》的《{category}》描写生硬，使用了诊断式语言",
                            suggestion="通过行为、微表情和环境互动渐进展现心理状态，避免直接贴标签",
                        )
                    )
                    score -= 15 if naturality_score > -3 else 25

        score = max(0, min(100, score))
        if not findings:
            return self._component_result(0, "PASS", [])
        status = "FAIL" if any(f["level"] == "FAIL" for f in findings) else "WARNING"
        return self._component_result(score, status, findings)

    def _review_relationship(self, content: str) -> dict:
        findings = []
        score = 55

        change_count = 0
        change_types = set()
        for pattern in RELATIONSHIP_CHANGE:
            matches = pattern.findall(content)
            if matches:
                change_count += len(matches)
                change_types.add(pattern.pattern[:20])

        types_count = len(change_types)

        if change_count < self.min_changes:
            findings.append(
                self._make_finding(
                    "WARN",
                    f"人物关系无变化: 仅{change_count}处关系信号",
                    suggestion="每章至少让一对人物关系有微小变化: 多一分信任、少一分怀疑或多一个人情",
                )
            )
            score -= 20
        elif types_count >= 3:
            score += 10

        if types_count == 1 and change_count > 0:
            findings.append(
                self._make_finding(
                    "WARN",
                    "人物关系单一: 只出现1种关系变化重复堆叠",
                    suggestion="丰富关系维度: 信任、人情、误会、利益、承诺交替出现",
                )
            )
            score -= 10

        score = max(0, min(100, score))
        status = "PASS" if score >= 75 else ("WARNING" if score >= 45 else "FAIL")
        return self._component_result(score, status, findings)

    @staticmethod
    def _load_character_psychologies() -> list:
        try:
            from src.guards.human_texture.character_psychology_crud import list_character_psychologies
            project_root = Path(__file__).resolve().parents[2]
            return list_character_psychologies(project_root)
        except Exception:
            return []

    @staticmethod
    def _calc_emotion_intensity(text: str) -> int:
        total = 0
        for word, weight in EXTREME_EMOTION_WORDS.items():
            total += text.count(word) * weight
        return total

    @staticmethod
    def _get_char_text_segments(content: str, char_name: str, window: int = 200) -> str:
        segments = []
        pos = 0
        while True:
            idx = content.find(char_name, pos)
            if idx == -1:
                break
            start = max(0, idx - window)
            end = min(len(content), idx + len(char_name) + window)
            segments.append(content[start:end])
            pos = end
        return " ".join(segments)

    @staticmethod
    def _check_naturality(text: str, severity: int) -> int:
        progressive_count = sum(1 for word in PROGRESSIVE_WORDS if word in text)
        abrupt_count = sum(1 for word in ABRUPT_WORDS if word in text)
        label_count = sum(1 for word in DIAGNOSTIC_LABELS if word in text)
        if severity <= 2 and progressive_count > 0:
            return 1
        if label_count > 0:
            return -5
        if abrupt_count > 3:
            return -2
        if severity >= 4 and progressive_count == 0:
            return -1
        return 0
