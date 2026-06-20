"""Chapter context engine: brief generation, extraction functions, context injection."""
import re
import json
import sqlite3
from pathlib import Path

from src.pipeline._base import connect, now, _get_novel_id


# ============================================================
# CHAPTER_BRIEF — 生成章节摘要 JSON
# ============================================================
def generate_chapter_brief(chapter_no, title, content, wc, chapter_type, prev_ending="", app_inst=None):
    """生成结构化 chapter_brief JSON 并保存到文件"""
    lines = [l for l in content.split("\n") if l.strip() and not l.startswith("=")]
    opening = lines[0][:200] if lines else ""
    ending = lines[-3][:200] if len(lines) >= 3 else opening[-200:]

    scene_markers = re.findall(r'(第.*天|早上|傍晚|晚上|深夜|第二天|次日|清晨|黄昏)', content)
    dialogue_count = len(re.findall(r'"[^"]{5,}"', content))

    conn = connect(app_inst)
    cur = conn.cursor()
    nid = _get_novel_id(cur, app_inst)
    ch_plan = cur.execute(
        "SELECT planned_title, chapter_goal, conflict_point, ending_hook_direction, continuity_from_previous "
        "FROM chapter_plans WHERE novel_id=? AND volume_no=? AND chapter_no=?",
        (nid, app_inst.volume_no, chapter_no)).fetchone()
    conn.close()

    planned_title = ch_plan['planned_title'] if ch_plan else ""
    title_match = "match" if title == planned_title else "changed"
    planned_vs_actual = {
        "planned_title": planned_title,
        "actual_title": title,
        "title_match": title_match,
        "planned_goal": ch_plan['chapter_goal'] if ch_plan else "",
        "planned_conflict": ch_plan['conflict_point'] if ch_plan else "",
        "planned_hook": ch_plan['ending_hook_direction'] if ch_plan else "",
    }

    brief = {
        "novel_slug": app_inst.novel_slug,
        "volume_no": app_inst.volume_no,
        "chapter_no": chapter_no,
        "chapter_type": chapter_type,
        "final_title": title,
        "planned_title": planned_title,
        "title_match_status": title_match,
        "actual_word_count": wc,
        "opening_state": opening,
        "ending_state": ending,
        "actual_main_events": f"{len(scene_markers)}场景, {dialogue_count}段对话",
        "actual_conflicts": "详见正文",
        "next_chapter_hooks": ending[-400:] if ending else "",
        "continuity_notes": "",
        "planned_vs_actual_diff": json.dumps(planned_vs_actual, ensure_ascii=False),
        "created_at": now()
    }

    briefs_dir = app_inst.exports_root / "chapter_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)
    brief_path = briefs_dir / f"chapter_{chapter_no:03d}_brief.json"
    brief_path.write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  [OK] chapter_brief: {brief_path}")

    conn2 = connect(app_inst)
    cur2 = conn2.cursor()
    nid2 = _get_novel_id(cur2, app_inst)
    cur2.execute("SELECT id FROM chapters WHERE novel_id=? AND chapter_no=?", (nid2, chapter_no))
    ch = cur2.fetchone()
    if ch:
        cur2.execute(
            "UPDATE chapter_summaries SET key_events=?, continuity_notes=? WHERE novel_id=? AND chapter_id=?",
            (ending, json.dumps(planned_vs_actual, ensure_ascii=False), nid2, ch['id']))
        conn2.commit()
    conn2.close()

    return brief


# ============================================================
# STEP 7.9: CONTEXT GENERATION — 章节上下文提取
# ============================================================
_ITEM_LEXICON = [
    "柴刀", "斧头", "剑", "刀", "匕首", "棍", "枪", "弓", "弩",
    "役牌", "令牌", "木牌", "玉简", "卷轴", "书", "信", "符", "禁制符", "传送符",
    "法器", "法宝", "灵器", "仙器", "神器", "魔器",
    "丹药", "筑基丹", "破境丹", "疗伤丹", "止血丸", "辟谷丹", "筑基液", "灵液",
    "灵石", "灵晶", "灵脉", "矿", "药材", "灵草",
    "储物袋", "乾坤袋", "空间戒指", "储物戒指", "纳戒",
    "信物", "玉佩", "戒指", "项链", "手镯", "发簪", "令牌", "钥匙",
    "残片", "碎片", "图", "地图", "皮纸", "陶片", "瓷片", "铁钉", "木盒", "盒",
    "鼎", "炉", "丹炉", "药鼎", "阵盘", "阵旗", "阵眼",
    "血", "精血", "魔种", "封印", "结界", "屏障",
    "遗物", "护身符", "骨", "灰", "衣", "袍", "靴", "冠", "面具",
    "酒", "茶", "碗", "杯", "壶", "食物", "干粮", "水囊",
    "绳", "锁", "链", "笼", "枷锁", "镣铐",
    "船", "车", "轿", "马", "兽", "坐骑", "灵兽", "妖兽",
    "镜", "珠", "灯笼", "灯", "火折", "烛", "火把",
    "琴", "笛", "箫", "棋盘", "棋子", "笔", "墨", "砚", "纸",
]


def _extract_character_locations(content, char_names):
    """Extract last-known location per character from chapter text."""
    locs = {}
    LOC_PATTERNS = [
        r"(?:回到|来到|走到|跑到|行至|赶往|前往|进入|踏入|步入|迈入"
        r"|坐在|站在|躺在|靠在|蹲在|藏在|住在|立在|待在|留在|等在|跪在"
        r"|躲进|钻进|缩进|退到|冲到|奔向"
        r")(.{1,12}?)(?:[,，。.；;、\s]|$)",
        r"(?:在|于)(.{1,12}?)(?:[,，。.；;、\s]|$)",
        r"(?:坐|站|躺|靠|蹲|藏|住|立|待|留|等"
        r"|回|进|入|去|来|走|跑|行|往|至|赴|过|离|出|归"
        r")(?:在|到|于|至|往|向)?(.{1,12}?)(?:[,，。.；;、\s]|$)",
    ]

    for name in char_names:
        if name not in content:
            continue
        last_pos = content.rfind(name)
        if last_pos < 0:
            continue
        window = content[last_pos:last_pos + 60]
        for pat in LOC_PATTERNS:
            m = re.search(pat, window)
            if m:
                loc_text = m.group(1).strip()
                if len(loc_text) >= 2 and not loc_text.startswith("了"):
                    loc_text = re.sub(
                        r"[坐站蹲藏躲走跑抬望看听摸推拉翻找拿放打敲砍刺][下起开着过了完]?$",
                        "", loc_text)
                    if len(loc_text) >= 2:
                        locs[name] = loc_text
                    break
    return locs


def _extract_active_items(content):
    """Find items mentioned with action verbs (拿出/掏出/找到/发现/握着/收起)."""
    items = set()
    action_pattern = r"(?:拿出|掏出|找到|发现|握着|捏着|收起|藏起|祭出|取出|掏)"
    for item in _ITEM_LEXICON:
        if item in content:
            item_positions = [m.start() for m in re.finditer(re.escape(item), content)]
            for pos in item_positions:
                window = content[max(0, pos - 20):pos + len(item) + 20]
                if re.search(action_pattern, window):
                    items.add(item)
                    break
            if item not in items and content.count(item) >= 3:
                items.add(item)
    return sorted(items)[:10]


def _extract_unresolved_threads(content):
    """Find dangling questions and unresolved hints."""
    threads = []
    for m in re.finditer(r".{10,80}？", content):
        q = m.group().strip()
        if q:
            threads.append(q[:80])
    for m in re.finditer(r"(?:还没|尚未|仍不|仍未|未解|未明|不知|不知晓|等.{2,6}再|以后再)(.{5,60}?)(?:[,，。.；;、]|$)", content):
        t = m.group().strip()
        if len(t) >= 6:
            threads.append(t[:80])
    return threads[:10]


_EMOTION_WORDS = [
    "愤怒", "暴怒", "怒火", "恼怒", "生气",
    "悲伤", "难过", "哀伤", "悲痛", "心痛", "心酸",
    "恐惧", "害怕", "惊恐", "畏惧", "胆怯",
    "惊讶", "震惊", "吃惊", "愕然",
    "厌恶", "反感", "嫌弃", "憎恨", "恨",
    "喜悦", "高兴", "开心", "欣喜", "兴奋", "欢喜",
    "焦虑", "焦躁", "烦躁", "不安", "忐忑",
    "冷静", "沉着", "镇定", "沉稳", "平静", "淡然",
    "紧张", "紧绷", "戒备", "警惕",
    "放松", "释然", "宽慰", "安心",
    "失望", "失落", "沮丧", "灰心",
    "愧疚", "内疚", "自责", "悔恨",
    "好奇", "疑惑", "困惑", "茫然", "迷茫",
    "坚定", "决然", "果断", "刚毅",
    "疲惫", "疲倦", "倦怠", "乏",
    "孤独", "寂寞", "孤单",
    "感动", "触动",
    "怀念", "思念", "牵挂",
    "无奈", "苦笑",
]


def _extract_emotional_states(content, char_names):
    """Find last emotion word near each character."""
    states = {}
    for name in char_names:
        if name not in content:
            continue
        last_pos = content.rfind(name)
        if last_pos < 0:
            continue
        window = content[last_pos:last_pos + 80]
        for ew in _EMOTION_WORDS:
            if ew in window:
                states[name] = ew
                break
    return states


def _extract_world_state(content):
    """Extract 2-3 sentences about environment changes from last 500 chars."""
    tail = content[-500:]
    sentences = re.split(r"[。.]", tail)
    changed = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        if re.search(r"[变化改转现显现涌现消散蔓延]", s) and len(s) >= 6:
            changed.append(s[:120])
    return "。".join(changed[:3])


# ═══════════════════════════════════════════════════
# v0.7.2: Story Arc — enhanced extraction
# ═══════════════════════════════════════════════════

_PHYSICAL_STATE_KEYWORDS = {
    "轻伤": ["擦伤", "扭到", "磕到", "划破", "皮外伤", "淤青", "小伤"],
    "中伤": ["骨折", "流血", "伤口", "打伤", "内伤", "脱臼", "吐血", "咳血", "断骨"],
    "重伤": ["濒死", "昏迷", "大出血", "经脉尽断", "丹田破裂", "五脏俱裂", "奄奄一息"],
    "中毒": ["中毒", "毒发", "毒性", "解毒", "麻", "毒气"],
    "疾病": ["发烧", "生病", "感染", "过敏", "晕倒", "晕眩", "虚弱", "发冷", "咳嗽"],
    "恢复": ["痊愈", "恢复", "好了", "没事", "疗伤", "养伤", "愈合", "康复"],
    "健康": ["完好", "无恙", "平安", "精神", "活动自如"],
}


def _extract_character_physical_states(content, char_names):
    """Extract physical state per character from chapter text."""
    states = {}
    for name in char_names:
        if name not in content:
            continue
        last_pos = content.rfind(name)
        if last_pos < 0:
            continue
        window = content[last_pos:last_pos + 100]
        for state_label, keywords in _PHYSICAL_STATE_KEYWORDS.items():
            for kw in keywords:
                if kw in window:
                    states[name] = state_label
                    break
            if name in states:
                break
    return states


_DECISION_MARKERS = [
    r"(决定|决定了|决定要|做出.{1,6}决定)",
    r"(选择了|选择.{1,10}选择)",
    r"(最终.{1,10}(还是|决定|选择))",
    r"(从今以后|从此|今后.{1,6}(不再|要|不会|必须))",
    r"(下定.{1,6}决心|下了.{1,6}决心)",
]


def _extract_key_decisions(content, char_names):
    """Find key decisions made by characters in this chapter."""
    decisions = []
    for name in char_names:
        if name not in content:
            continue
        for pos in [m.start() for m in re.finditer(re.escape(name), content)]:
            window_start = max(0, pos - 20)
            window_end = min(len(content), pos + 80)
            window = content[window_start:window_end]
            for marker_pat in _DECISION_MARKERS:
                m = re.search(marker_pat, window)
                if m:
                    decisions.append({
                        "character": name,
                        "decision": m.group(1),
                        "context": window.strip()[:120],
                    })
                    break
    return decisions[:10]


def _extract_emotional_states_enhanced(content, char_names):
    """Extract emotional states with intensity and transition detection."""
    _INTENSIFIERS = {
        5: ["极度", "透顶", "到了极点", "无法承受", "崩溃"],
        4: ["非常", "极为", "无比", "深深", "浓烈", "剧烈"],
        3: ["十分", "很", "相当", "明显", "显然"],
        2: ["有些", "有点", "几分", "微微", "略微", "一丝"],
        1: ["稍", "略带", "浅淡", "隐约"],
    }
    states = {}
    for name in char_names:
        if name not in content:
            continue
        last_pos = content.rfind(name)
        if last_pos < 0:
            continue
        window = content[last_pos:last_pos + 80]
        best_emotion = None
        best_intensity = 1
        for ew in _EMOTION_WORDS:
            if ew in window:
                best_emotion = ew
                ew_pos = window.find(ew)
                nearby = window[max(0, ew_pos - 15):ew_pos + len(ew) + 15]
                for level, words in _INTENSIFIERS.items():
                    if any(w in nearby for w in words):
                        best_intensity = max(best_intensity, level)
                break
        if best_emotion:
            states[name] = {
                "state": best_emotion,
                "intensity": best_intensity,
            }
    return states


def _extract_active_relationships(content, char_names):
    """Find which characters interact in this chapter."""
    rels = []
    for i, n1 in enumerate(char_names):
        for n2 in char_names[i + 1:]:
            pos1 = [m.start() for m in re.finditer(re.escape(n1), content)]
            pos2_set = set(m.start() for m in re.finditer(re.escape(n2), content))
            for p1 in pos1:
                for p2 in pos2_set:
                    if abs(p1 - p2) <= 200:
                        rels.append(f"{n1}-{n2}")
                        break
                if f"{n1}-{n2}" in rels:
                    break
    return rels[:20]


def _upsert_arc_character_states(
    nid,
    chapter_no,
    char_names,
    phys_states,
    emotions_enh,
    key_decisions,
    active_rels,
    app_inst=None,
):
    """Populate arc_character_states table for each character in this chapter."""
    conn = connect(app_inst)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS arc_character_states (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id INTEGER NOT NULL REFERENCES novels(id),
        character_id INTEGER NOT NULL REFERENCES characters(id),
        chapter_no INTEGER NOT NULL,
        physical_state TEXT DEFAULT '',
        emotional_state TEXT DEFAULT '',
        arc_progress TEXT DEFAULT '',
        key_decisions TEXT DEFAULT '[]',
        active_relationships TEXT DEFAULT '[]',
        UNIQUE(novel_id, character_id, chapter_no)
    )""")
    conn.commit()

    for name in char_names:
        cur.execute("SELECT id FROM characters WHERE novel_id=? AND name=?", (nid, name))
        row = cur.fetchone()
        if not row:
            continue
        cid = row[0]
        phys = phys_states.get(name, "")
        emo_data = emotions_enh.get(name, {})
        emo_json = json.dumps(emo_data, ensure_ascii=False) if emo_data else "{}"
        char_decisions = [d for d in key_decisions if d["character"] == name]
        decisions_json = json.dumps(char_decisions, ensure_ascii=False)
        char_rels = [r for r in active_rels if name in r]
        rels_json = json.dumps(char_rels, ensure_ascii=False)
        arc_parts = []
        if phys:
            arc_parts.append(f"身体:{phys}")
        if emo_data:
            arc_parts.append(f"情绪:{emo_data.get('state','')}")
        if char_decisions:
            arc_parts.append(f"决定:{len(char_decisions)}项")
        arc_progress = " | ".join(arc_parts)

        cur.execute("""SELECT id FROM arc_character_states
                       WHERE novel_id=? AND character_id=? AND chapter_no=?""",
                    (nid, cid, chapter_no))
        existing = cur.fetchone()
        if existing:
            cur.execute("""UPDATE arc_character_states SET
                physical_state=?, emotional_state=?, arc_progress=?,
                key_decisions=?, active_relationships=?
                WHERE novel_id=? AND character_id=? AND chapter_no=?""",
                        (phys, emo_json, arc_progress, decisions_json, rels_json,
                         nid, cid, chapter_no))
        else:
            cur.execute("""INSERT INTO arc_character_states
                (novel_id, character_id, chapter_no, physical_state, emotional_state,
                 arc_progress, key_decisions, active_relationships)
                VALUES(?,?,?,?,?,?,?,?)""",
                        (nid, cid, chapter_no, phys, emo_json, arc_progress,
                         decisions_json, rels_json))
    conn.commit()
    conn.close()


def _ensure_chapter_contexts_table(cur):
    cur.execute("""CREATE TABLE IF NOT EXISTS chapter_contexts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        novel_id INTEGER NOT NULL REFERENCES novels(id),
        chapter_id INTEGER NOT NULL REFERENCES chapters(id),
        chapter_no INTEGER NOT NULL,
        character_locations TEXT DEFAULT '{}',
        active_items TEXT DEFAULT '[]',
        unresolved_threads TEXT DEFAULT '[]',
        emotional_states TEXT DEFAULT '{}',
        world_state TEXT DEFAULT '',
        ending_state TEXT DEFAULT '',
        hooks_for_next TEXT DEFAULT '',
        raw_summary TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(novel_id, chapter_id)
    )""")


def generate_chapter_context(chapter_no, title, content, wc, nid, ch_id, char_names=None, app_inst=None):
    """Generate structured chapter_context row and INSERT into chapter_contexts table."""
    conn = connect(app_inst)
    cur = conn.cursor()
    _ensure_chapter_contexts_table(cur)

    if not char_names:
        cur.execute("SELECT name FROM characters WHERE novel_id=?", (nid,))
        char_names = [r[0] for r in cur.fetchall()]

    char_locs = _extract_character_locations(content, char_names)
    items = _extract_active_items(content)
    threads = _extract_unresolved_threads(content)
    emotions = _extract_emotional_states(content, char_names)
    world = _extract_world_state(content)

    phys_states = _extract_character_physical_states(content, char_names)
    emotions_enh = _extract_emotional_states_enhanced(content, char_names)
    key_decisions = _extract_key_decisions(content, char_names)
    active_rels = _extract_active_relationships(content, char_names)

    ending_state = ""
    hooks_for_next = ""
    brief_path = app_inst.exports_root / "chapter_briefs" / f"chapter_{chapter_no:03d}_brief.json"
    if brief_path.exists():
        try:
            brief = json.loads(brief_path.read_text(encoding="utf-8"))
            ending_state = brief.get("ending_state", "")
            hooks_for_next = brief.get("next_chapter_hooks", "")
        except Exception:
            pass

    raw_summary = ""
    cur.execute(
        "SELECT short_summary FROM chapter_summaries WHERE novel_id=? AND chapter_id=?",
        (nid, ch_id))
    sm_row = cur.fetchone()
    if sm_row and sm_row[0]:
        raw_summary = sm_row[0]
    else:
        lines = [l for l in content.split("\n") if l.strip() and not l.startswith("=")]
        raw_summary = (lines[0][:80] if lines else "") + " ... " + (lines[-1][:80] if len(lines) > 1 else "")

    cur.execute("SELECT id FROM chapter_contexts WHERE novel_id=? AND chapter_id=?", (nid, ch_id))
    existing = cur.fetchone()
    ts = now()
    if existing:
        cur.execute("""
            UPDATE chapter_contexts SET
                character_locations=?, active_items=?, unresolved_threads=?,
                emotional_states=?, world_state=?, ending_state=?,
                hooks_for_next=?, raw_summary=?, created_at=?
            WHERE novel_id=? AND chapter_id=?
        """, (
            json.dumps(char_locs, ensure_ascii=False),
            json.dumps(items, ensure_ascii=False),
            json.dumps(threads, ensure_ascii=False),
            json.dumps(emotions, ensure_ascii=False),
            world,
            ending_state,
            hooks_for_next,
            raw_summary,
            ts,
            nid, ch_id))
    else:
        cur.execute("""
            INSERT INTO chapter_contexts(novel_id, chapter_id, chapter_no,
                character_locations, active_items, unresolved_threads,
                emotional_states, world_state, ending_state, hooks_for_next,
                raw_summary, created_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            nid, ch_id, chapter_no,
            json.dumps(char_locs, ensure_ascii=False),
            json.dumps(items, ensure_ascii=False),
            json.dumps(threads, ensure_ascii=False),
            json.dumps(emotions, ensure_ascii=False),
            world,
            ending_state,
            hooks_for_next,
            raw_summary,
            ts))
    conn.commit()
    conn.close()

    _upsert_arc_character_states(
        nid,
        chapter_no,
        char_names,
        phys_states,
        emotions_enh,
        key_decisions,
        active_rels,
        app_inst=app_inst,
    )

    print(f"  [OK] chapter_context: {len(char_locs)}人物位置, {len(items)}物品, {len(threads)}悬念, {len(phys_states)}身体状态")
    return {
        "chapter_no": chapter_no,
        "character_locations": char_locs,
        "active_items": items,
        "unresolved_threads": threads,
        "emotional_states": emotions,
    }


def _build_context_injection(cur, nid, chapter_no, max_chapters=3):
    """Build ≤300-char context summary from last N chapter_contexts for pre injection."""
    start_ch = max(1, chapter_no - max_chapters)
    try:
        cur.execute("""
            SELECT character_locations, active_items, unresolved_threads, raw_summary
            FROM chapter_contexts
            WHERE novel_id=? AND chapter_no BETWEEN ? AND ?
            ORDER BY chapter_no
        """, (nid, start_ch, chapter_no - 1))
    except Exception as exc:
        if "no such table" in str(exc):
            return None
        raise
    rows = cur.fetchall()
    if not rows:
        return None

    summaries = []
    all_items = set()
    all_threads = set()
    latest_locs = {}

    for row in rows:
        if row[3]:
            summaries.append(row[3][:100])
        try:
            items = json.loads(row[1]) if isinstance(row[1], str) else (row[1] or [])
            for it in items:
                all_items.add(it)
            threads = json.loads(row[2]) if isinstance(row[2], str) else (row[2] or [])
            for th in threads:
                all_threads.add(th)
            locs = json.loads(row[0]) if isinstance(row[0], str) else (row[0] or {})
            latest_locs.update(locs)
        except Exception:
            pass

    parts = []
    if summaries:
        parts.append("前情：" + "；".join(summaries[-2:]))
    if all_threads:
        parts.append("悬而未决：" + "、".join(sorted(all_threads)[:3]))
    if latest_locs:
        loc_str = " | ".join(f"{k}@{v}" for k, v in list(latest_locs.items())[:8])
        parts.append(f"人物位置：{loc_str}")
    if all_items:
        parts.append("活跃物品：" + "、".join(sorted(all_items)[:5]))

    return "\n    ".join(parts)
