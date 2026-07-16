#!/usr/bin/env python3
"""Merged character agent."""

import re
import sqlite3
import json
from contextlib import closing
from pathlib import Path

from .base_analyzer import BaseAnalyzer
DEFAULT_DB_PATH = "./data/novel_memory.db"


def connect_sqlite(db_path):
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def find_project_root(start):
    current = Path(start).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "src").exists() and (candidate / "config.example.json").exists():
            return candidate
    return current


def find_character_mention_positions(content, names):
    positions = {name: [] for name in names}
    consumed = [False] * len(content)
    mention_boundaries = set("，。！？；：、\n\r \t\"'“”‘’「」『』（）()[]{}")
    for name in sorted((name for name in names if name), key=len, reverse=True):
        start = 0
        while True:
            index = content.find(name, start)
            if index < 0:
                break
            end = index + len(name)
            if len(name) == 1 and index > 0 and content[index - 1] not in mention_boundaries:
                start = index + 1
                continue
            if not any(consumed[index:end]):
                positions[name].append(index)
                for offset in range(index, end):
                    consumed[offset] = True
            start = max(end, index + 1)
    return positions

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


class CharacterAnalyzer(BaseAnalyzer):
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
        mention_positions = find_character_mention_positions(
            content,
            [card.get("name", "") for card in cards if card.get("name")],
        )

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

                char_text = self._get_char_text_segments(
                    content,
                    name,
                    mention_positions=mention_positions,
                )
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
            project_root = find_project_root(Path(__file__).resolve())
            psychology_module = project_root / "src" / "guards" / "human_texture" / "character_psychology_crud.py"
            if not psychology_module.exists():
                return []
            return []
        except Exception:
            return []

    @staticmethod
    def _calc_emotion_intensity(text: str) -> int:
        total = 0
        for word, weight in EXTREME_EMOTION_WORDS.items():
            total += text.count(word) * weight
        return total

    @staticmethod
    def _get_char_text_segments(
        content: str,
        char_name: str,
        window: int = 200,
        mention_positions: dict[str, list[int]] | None = None,
        all_names: list[str] | None = None,
    ) -> str:
        segments = []
        if mention_positions is None:
            names = list(all_names or [char_name])
            if char_name not in names:
                names.append(char_name)
            mention_positions = find_character_mention_positions(content, names)
        for idx in mention_positions.get(char_name, []):
            start = max(0, idx - window)
            end = min(len(content), idx + len(char_name) + window)
            segments.append(content[start:end])
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
def load_voice_context(
    config: dict,
    novel_slug: str,
    db_path: str = None,
    character_names: list[str] = None,
) -> dict:
    """
    Load complete voice context for a novel.
    Returns:
      {
        "enabled": bool,
        "source": "db" | "json" | "example" | "none",
        "novel_slug": str,
        "profiles": [dict, ...],
        "packs": {pack_id: dict, ...},
        "narration_policy": dict,
        "warnings": [str, ...],
      }
    """
    voice_cfg = config.get("voice_system", {})
    if not voice_cfg.get("enabled", True):
        return _empty_context("disabled", novel_slug)

    warnings = []
    profiles = []
    packs = {}
    source = "none"
    db_path = db_path or config.get("db_path", DEFAULT_DB_PATH)

    # 1. Try database
    if voice_cfg.get("use_database_profiles", True) and Path(db_path).exists():
        try:
            with closing(connect_sqlite(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                profiles = _load_profiles_from_db(conn, novel_slug)
                packs = _load_packs_from_db(conn)
            if profiles:
                source = "db"
        except Exception as e:
            warnings.append(f"Database load failed: {e}")

    # 2. Fallback to JSON
    if not profiles:
        json_path = voice_cfg.get("voice_profiles_template", "").replace("{novel_slug}", novel_slug)
        if not json_path:
            json_path = f"novels/{novel_slug}/voice_profiles.json"
        if Path(json_path).exists():
            try:
                profiles = json.loads(Path(json_path).read_text(encoding='utf-8'))
                if not isinstance(profiles, list):
                    profiles = [profiles]
                source = "json"
            except Exception as e:
                warnings.append(f"JSON load failed ({json_path}): {e}")

    # 3. Fallback to example
    if not profiles:
        example_path = voice_cfg.get("fallback_voice_profiles", "examples/demo_novel/voice_profiles.example.json")
        if Path(example_path).exists():
            try:
                profiles = json.loads(Path(example_path).read_text(encoding='utf-8'))
                if not isinstance(profiles, list):
                    profiles = [profiles]
                source = "example"
            except Exception as e:
                warnings.append(f"Example load failed: {e}")

    # 4. Load packs if not from DB
    if not packs:
        packs_dir = voice_cfg.get("voice_packs_dir", "packs/voice")
        packs = _load_packs_from_files(packs_dir)

    # Filter to requested characters
    if character_names:
        profiles = [p for p in profiles if p.get("character_name", "") in character_names]

    narration_policy = voice_cfg.get("default_narration_policy", voice_cfg.get("narration_policy", {
        "dialect_level": 0, "meme_level": 0, "english_level": 0, "wenyan_level": 1,
    }))

    if not profiles:
        warnings.append("No voice profiles found for any character")

    return {
        "enabled": True,
        "source": source,
        "novel_slug": novel_slug,
        "profiles": profiles,
        "packs": packs,
        "narration_policy": narration_policy,
        "warnings": warnings,
    }


def _load_profiles_from_db(conn, novel_slug: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT id FROM novels WHERE slug=?", (novel_slug,))
    if not cur.fetchone():
        return []
    cur.execute("""SELECT * FROM character_voice_profiles
                   WHERE novel_id=(SELECT id FROM novels WHERE slug=?)
                   AND status='active' ORDER BY character_name""", (novel_slug,))
    profiles = []
    for r in cur.fetchall():
        profiles.append({
            "character_name": r["character_name"],
            "voice_type": r["voice_type"],
            "dialect_pack": r["dialect_pack"],
            "register_pack": r["register_pack"],
            "meme_pack": r["meme_pack"],
            "english_pack": r["english_pack"],
            "dialect_level": r["dialect_level"],
            "meme_level": r["meme_level"],
            "english_level": r["english_level"],
            "wenyan_level": r["wenyan_level"],
            "favorite_words": json.loads(r["favorite_words_json"] or "[]"),
            "forbidden_words": json.loads(r["forbidden_words_json"] or "[]"),
            "allowed_english": json.loads(r["allowed_english_json"] or "[]"),
            "banned_english": json.loads(r["banned_english_json"] or "[]"),
            "sample_lines": json.loads(r["sample_lines_json"] or "[]"),
            "notes": r["notes"],
            "phase": r["phase"],
        })
    return profiles


def _load_packs_from_db(conn) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT * FROM voice_packs WHERE status='active'")
    packs = {}
    for r in cur.fetchall():
        packs[r["pack_id"]] = {
            "pack_id": r["pack_id"],
            "type": r["pack_type"],
            "name": r["name"],
            "markers": json.loads(r["markers_json"] or "[]"),
            "soft_markers": json.loads(r["soft_markers_json"] or "[]"),
            "danger_markers": json.loads(r["danger_markers_json"] or "[]"),
            "allowed_contexts": json.loads(r["allowed_contexts_json"] or "[]"),
            "forbidden_contexts": json.loads(r["forbidden_contexts_json"] or "[]"),
            "max_density_per_1000_chars": r["max_density_per_1000_chars"],
            "overuse_warning_threshold": r["overuse_warning_threshold"],
        }
    return packs


def _load_packs_from_files(packs_dir: str) -> dict:
    packs = {}
    packs_path = Path(packs_dir)
    if not packs_path.exists():
        return packs
    for fp in sorted(packs_path.rglob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding='utf-8'))
            pack_id = data.get("pack_id", fp.stem)
            packs[pack_id] = {
                "pack_id": pack_id,
                "type": data.get("type", ""),
                "name": data.get("name", ""),
                "markers": data.get("markers", []),
                "soft_markers": data.get("soft_markers", []),
                "danger_markers": data.get("danger_markers", []),
                "allowed_contexts": data.get("allowed_contexts", []),
                "forbidden_contexts": data.get("forbidden_contexts", []),
                "max_density_per_1000_chars": data.get("max_density_per_1000_chars", 6),
                "overuse_warning_threshold": data.get("overuse_warning_threshold", 5),
            }
        except Exception:
            pass
    return packs


def _empty_context(reason: str, novel_slug: str) -> dict:
    return {
        "enabled": False,
        "source": "none",
        "novel_slug": novel_slug,
        "profiles": [],
        "packs": {},
        "narration_policy": {},
        "warnings": [f"Voice system {reason}"],
    }


def get_profiles_for_characters(voice_context: dict, character_names: list[str]) -> list[dict]:
    """Filter voice_context.profiles to only the given character names."""
    return [p for p in voice_context.get("profiles", [])
            if p.get("character_name", "") in character_names]
