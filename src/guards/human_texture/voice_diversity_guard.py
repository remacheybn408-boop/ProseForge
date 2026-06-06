"""voice_diversity_guard.py — 角色声纹检测 v0.6.6

检查同一本小说里不同角色的说话方式是否过于雷同。
声纹卡按 slot 独立存储，不窜库。
"""
import re
import json
from pathlib import Path
from collections import Counter


# ── 声纹卡字段定义 ──
VOICE_CARD_FIELDS = [
    "sentence_length_preference",
    "dialect",                     # 方言特征
    "dialect_words",               # 特色方言词
    "common_words",
    "forbidden_words",
    "emotional_leak_style",
    "anger_style",
    "lie_style",
    "silence_style",
    "humor_style",
    "relationship_specific_tone",
    "catchphrase",                 # 口头禅
    "catchphrase_context",         # 口头禅触发场景（如 惊讶/得意/紧张）
]

# ── 性格维度定义 ──
PERSONALITY_FIELDS = [
    "core",              # 核心性格: 沉稳/暴躁/谨慎/冲动/温和/狡诈
    "decision_style",    # 决策模式: 深思熟虑/直觉行动/优柔寡断
    "action_tendency",   # 行动倾向: 主动/被动/观望/激进
]

# ── 做事风格维度定义 ──
BEHAVIOR_FIELDS = [
    "social_style",      # 社交风格: 随和/强势/孤僻/热情
    "stress_response",   # 压力反应: 沉默/爆发/逃避/冷静
    "moral_compass",     # 道德底线: 有底线/不择手段/亦正亦邪
    "habits",            # 习惯动作: list[str]
]

# ── 叙事层维度定义（新增 v0.7.2）──
STORY_FIELDS = [
    "motivation",        # 核心动机: 角色行为的根本驱动力
    "fatal_flaw",        # 致命缺陷: 导致最大失败的性格弱点
    "secret",            # 秘密: 角色隐藏的关键信息
    "trauma",            # 关键创伤: 塑造角色的过去事件
    "goal_short",        # 短期目标: 当前章节驱动行动的目标
    "goal_long",         # 长期目标: 贯穿全书的终极目标
    "ability",           # 特长/能力
    "weakness",          # 不擅长/短板
    "arc_intended",      # 预定弧线: 角色从头到尾的成长轨迹
    "arc_current",       # 弧线当前状态: 已经经历了什么变化
]

# ── 精神状态维度（从独立模块重新导出）──
from .mental_state_crud import MENTAL_STATE_CATEGORIES

PERSONALITY_CHOICES = {
    "core": ["沉稳", "暴躁", "谨慎", "冲动", "温和", "狡诈", "天真", "冷酷"],
    "decision_style": ["深思熟虑", "直觉行动", "优柔寡断"],
    "action_tendency": ["主动", "被动", "观望", "激进"],
    "social_style": ["随和", "强势", "孤僻", "热情", "圆滑"],
    "stress_response": ["沉默", "爆发", "逃避", "冷静", "慌乱"],
    "moral_compass": ["有底线", "不择手段", "亦正亦邪", "利己"],
}


def get_voice_cards_dir(project_root: Path, set_name: str = None) -> Path:
    """获取当前活跃 slot 的声纹卡目录（指定卡组则返回卡组子目录）."""
    try:
        ws_dir = project_root / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return None
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return None
        vc_dir = ws_dir / active / "voice_cards"
        if set_name:
            vc_dir = vc_dir / set_name
        vc_dir.mkdir(parents=True, exist_ok=True)
        return vc_dir
    except Exception:
        return None



def get_active_voice_card_set(project_root: Path) -> str:
    """from project.json active_voice_card_set, default 'default'."""
    try:
        ws_dir = project_root / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return "default"
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return "default"
        proj_file = ws_dir / active / "project.json"
        if proj_file.exists():
            proj = json.loads(proj_file.read_text(encoding="utf-8"))
            return proj.get("active_voice_card_set", "default")
    except Exception:
        pass
    return "default"


def set_active_voice_card_set(project_root: Path, set_name: str) -> bool:
    """Set active voice card set for current novel."""
    try:
        ws_dir = project_root / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return False
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return False
        proj_file = ws_dir / active / "project.json"
        if proj_file.exists():
            proj = json.loads(proj_file.read_text(encoding="utf-8"))
        else:
            proj = {}
        proj["active_voice_card_set"] = set_name
        from datetime import datetime
        proj["updated_at"] = datetime.now().isoformat()
        proj_file.write_text(json.dumps(proj, ensure_ascii=False, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def list_voice_card_sets(project_root: Path) -> list[str]:
    """List all voice card sets for current slot."""
    try:
        ws_dir = project_root / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return []
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return []
        vc_dir = ws_dir / active / "voice_cards"
        if not vc_dir.exists():
            return ["default"]
        sets = []
        for item in sorted(vc_dir.iterdir()):
            if item.is_dir():
                sets.append(item.name)
        if not sets:
            sets.append("default")
        return sets
    except Exception:
        return ["default"]


def delete_voice_card(project_root: Path, name: str) -> bool:
    """删除角色卡（声纹+性格+做事完整删除）. 兼容旧版 voice 命令."""
    return _delete_card_file(project_root, name)


def _delete_card_file(project_root: Path, name: str) -> bool:
    """底层：删除角色卡 JSON 文件."""
    set_name = get_active_voice_card_set(project_root)
    vc_dir = get_voice_cards_dir(project_root, set_name)
    if not vc_dir:
        return False
    f = vc_dir / f"{name}.json"
    if f.exists():
        f.unlink()
        return True
    return False


# ──────────────────────────────────────────────
#  角色卡综合管理（声纹+性格+做事，v0.6.6+）
# ──────────────────────────────────────────────

def _is_flat_card(card: dict) -> bool:
    """检测是否为旧版扁平格式（无 voice/personality/behavior 子对象）."""
    return "voice" not in card and "personality" not in card and "behavior" not in card


def _upgrade_flat_card(name: str, card: dict) -> dict:
    """将旧版扁平格式升级为嵌套格式。"""
    voice_fields = {k: card.get(k, "") for k in VOICE_CARD_FIELDS if k in card}
    return {
        "name": name,
        "voice": voice_fields,
        "personality": {k: "" for k in PERSONALITY_FIELDS},
        "behavior": {k: ([] if k == "habits" else "") for k in BEHAVIOR_FIELDS},
    }


def _ensure_nested(card: dict, name: str = "") -> dict:
    """确保角色卡为嵌套格式，扁平卡自动升级，缺少的分组自动补齐."""
    if _is_flat_card(card):
        card = _upgrade_flat_card(name or card.get("name", ""), card)
    # 自动补齐缺少的分组
    if "story" not in card:
        card["story"] = {k: "" for k in STORY_FIELDS}
    if "voice" not in card:
        card["voice"] = {k: "" for k in VOICE_CARD_FIELDS}
    if "personality" not in card:
        card["personality"] = {k: "" for k in PERSONALITY_FIELDS}
    if "behavior" not in card:
        card["behavior"] = {k: ([] if k == "habits" else "") for k in BEHAVIOR_FIELDS}
    return card


def get_character_card(project_root: Path, name: str) -> dict | None:
    """获取完整角色卡（声纹+性格+做事），旧格式自动升级."""
    set_name = get_active_voice_card_set(project_root)
    vc_dir = get_voice_cards_dir(project_root, set_name)
    if not vc_dir:
        return None
    f = vc_dir / f"{name}.json"
    if not f.exists():
        return None
    raw = json.loads(f.read_text(encoding="utf-8"))
    card = _ensure_nested(raw, name)
    card["_file"] = f.name
    return card


def list_character_cards(project_root: Path) -> list[dict]:
    """列出当前 slot 所有完整角色卡，旧格式自动升级."""
    set_name = get_active_voice_card_set(project_root)
    vc_dir = get_voice_cards_dir(project_root, set_name)
    if not vc_dir or not vc_dir.exists():
        return []
    cards = []
    for f in sorted(vc_dir.glob("*.json")):
        try:
            raw = json.loads(f.read_text(encoding="utf-8"))
            card = _ensure_nested(raw, f.stem)
            card["_file"] = f.name
            cards.append(card)
        except Exception:
            pass
    return cards


def save_character_card(project_root: Path, name: str, card: dict) -> bool:
    """保存完整角色卡（嵌套格式），覆盖旧扁平格式."""
    set_name = get_active_voice_card_set(project_root)
    vc_dir = get_voice_cards_dir(project_root, set_name)
    if not vc_dir:
        return False
    card["name"] = name
    f = vc_dir / f"{name}.json"
    f.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def _extract_voice_from_nested(card: dict) -> dict:
    """从嵌套角色卡中提取声纹子对象（给旧 voice 命令向后兼容用）."""
    if _is_flat_card(card):
        return card
    voice = dict(card.get("voice", {}))
    voice["name"] = card.get("name", "")
    return voice


# 覆盖旧版列表/获取函数，支持嵌套格式
def list_voice_cards(project_root: Path) -> list[dict]:  # noqa: F811
    """列出当前 slot 所有声纹卡（从完整角色卡提取 voice 子对象）. \u540e\u5411\u517c\u5bb9."""
    char_cards = list_character_cards(project_root)
    return [_extract_voice_from_nested(c) for c in char_cards]


def get_voice_card(project_root: Path, name: str) -> dict | None:  # noqa: F811
    """获取单个声纹卡（从完整角色卡提取 voice 子对象）. \u540e\u5411\u517c\u5bb9."""
    cc = get_character_card(project_root, name)
    if not cc:
        return None
    return _extract_voice_from_nested(cc)


def save_voice_card(project_root: Path, name: str, card: dict) -> bool:  # noqa: F811
    """保存声纹卡（旧扁平格式 → 自动升级为嵌套格式保存）."""
    set_name = get_active_voice_card_set(project_root)
    vc_dir = get_voice_cards_dir(project_root, set_name)
    if not vc_dir:
        return False
    # 升级为完整角色卡
    nested = {
        "name": name,
        "voice": {k: card.get(k, "") for k in VOICE_CARD_FIELDS},
        "personality": {k: "" for k in PERSONALITY_FIELDS},
        "behavior": {k: ([] if k == "habits" else "") for k in BEHAVIOR_FIELDS},
    }
    f = vc_dir / f"{name}.json"
    f.write_text(json.dumps(nested, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


# ── 角色 DB 表字段定义 ──
# 映射: DB列名 → 用户可见字段名
DB_CHAR_FIELDS = {
    "alias": "别名",
    "role": "定位",
    "identity": "身份",
    "ability": "能力",
    "relationship": "关系",
    "arc": "成长弧",
    "motivation": "动机",
    "tags": "标签",
}
# personality 在 DB 中是自由文本（性格描述），与 JSON 的 structured personality 不同
DB_CHAR_FIELD_NAMES = list(DB_CHAR_FIELDS.keys())
DB_CHAR_FIELD_NAMES_EXT = DB_CHAR_FIELD_NAMES + ["description"]


def _get_active_db_path(project_root: Path) -> Path | None:
    """获取当前活跃 slot 的 novel.db 路径."""
    try:
        ws_dir = project_root / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return None
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return None
        db_path = ws_dir / active / "novel.db"
        return db_path if db_path.exists() else None
    except Exception:
        return None


def _ensure_char_db_row(project_root: Path, name: str) -> bool:
    """确保 characters 表中有该角色行，不存在则插入."""
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT id FROM characters WHERE name=?", (name,))
        if not cur.fetchone():
            conn.execute(
                "INSERT INTO characters (novel_id, name, status) VALUES (1, ?, 'active')",
                (name,),
            )
            conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_char_db_row(project_root: Path, name: str) -> dict | None:
    """从 characters 表获取完整行，返回 dict 或 None."""
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return _db_fallback(name)
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute(
            "SELECT name, alias, role, identity, personality, motivation, "
            "ability, relationship, arc, status, tags FROM characters WHERE name=?",
            (name,),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return _db_fallback(name)
        cols = ["name", "alias", "role", "identity", "personality_info",
                 "motivation", "ability", "relationship", "arc", "status", "tags"]
        d = {"name": name}
        for i, c in enumerate(cols):
            v = row[i]
            if v:
                d[c] = v
        return d
    except Exception:
        return _db_fallback(name)


def _db_fallback(name: str) -> dict:
    """DB 不可用时的回退行."""
    return {"name": name, "status": "active"}


def save_char_db_field(project_root: Path, name: str, field: str, value: str) -> bool:
    """保存单个字段到 characters 表。自动创建行 if not exists."""
    if not _ensure_char_db_row(project_root, name):
        return False

    db_path = _get_active_db_path(project_root)
    if not db_path:
        return False

    # 字段名映射
    col_map = {
        "alias": "alias", "role": "role", "identity": "identity",
        "ability": "ability", "relationship": "relationship",
        "arc": "arc", "motivation": "motivation", "tags": "tags",
        "description": "personality",  # personality 在 DB 中是自由文本
    }
    col = col_map.get(field)
    if not col:
        return False

    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute(f"UPDATE characters SET {col}=? WHERE name=?", (value, name))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def delete_char_db_row(project_root: Path, name: str) -> bool:
    """标记 characters 表角色为删除状态."""
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE characters SET status='deleted' WHERE name=?", (name,))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ── 角色聚焦状态 ──

FOCUS_STATE_CHOICES = ["活跃", "暂离", "退场"]

def _migrate_focus_state(project_root: Path) -> bool:
    """确保 characters 表有 focus_state 列."""
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        # Check if column exists
        cur = conn.execute("PRAGMA table_info(characters)")
        cols = [c[1] for c in cur.fetchall()]
        if "focus_state" not in cols:
            conn.execute("ALTER TABLE characters ADD COLUMN focus_state TEXT DEFAULT '活跃'")
            conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def get_focus_state(project_root: Path, name: str) -> str:
    """获取角色聚焦状态."""
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return "活跃"
    try:
        _migrate_focus_state(project_root)
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT focus_state FROM characters WHERE name=?", (name,))
        row = cur.fetchone()
        conn.close()
        return row[0] if row and row[0] else "活跃"
    except Exception:
        return "活跃"


def set_focus_state(project_root: Path, name: str, state: str) -> bool:
    """设置角色聚焦状态."""
    if state not in FOCUS_STATE_CHOICES:
        return False
    _migrate_focus_state(project_root)
    _ensure_char_db_row(project_root, name)
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE characters SET focus_state=? WHERE name=?", (state, name))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


# ── 角色关系表 ──

def _migrate_relation_table(project_root: Path) -> bool:
    """确保 character_relationships 表存在."""
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return False
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS character_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                novel_id INTEGER DEFAULT 1,
                char_a TEXT NOT NULL,
                char_b TEXT NOT NULL,
                relation_type TEXT NOT NULL DEFAULT '',
                description TEXT DEFAULT '',
                UNIQUE(novel_id, char_a, char_b)
            )
        """)
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def set_relation(project_root: Path, char_a: str, char_b: str,
                  relation_type: str) -> bool:
    """设置两个角色间的关系."""
    _migrate_relation_table(project_root)
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return False
    # 保证排序一致
    a, b = sorted([char_a, char_b])
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            INSERT INTO character_relationships (novel_id, char_a, char_b, relation_type)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(novel_id, char_a, char_b) DO UPDATE SET relation_type=excluded.relation_type
        """, (a, b, relation_type))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def delete_relation(project_root: Path, char_a: str, char_b: str) -> bool:
    """删除两个角色间的关系."""
    _migrate_relation_table(project_root)
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return False
    a, b = sorted([char_a, char_b])
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.execute("DELETE FROM character_relationships WHERE char_a=? AND char_b=?", (a, b))
        conn.commit()
        conn.close()
        return True
    except Exception:
        return False


def list_relations(project_root: Path) -> list[dict]:
    """列出所有角色关系."""
    _migrate_relation_table(project_root)
    db_path = _get_active_db_path(project_root)
    if not db_path:
        return []
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT char_a, char_b, relation_type FROM character_relationships")
        rows = cur.fetchall()
        conn.close()
        return [{"char_a": r[0], "char_b": r[1], "type": r[2]} for r in rows]
    except Exception:
        return []


def get_relations_for(project_root: Path, name: str) -> list[dict]:
    """获取一个角色的所有关系."""
    all_rels = list_relations(project_root)
    return [r for r in all_rels if r["char_a"] == name or r["char_b"] == name]


# ── 角色卡导入导出 ──

def export_char_card(project_root: Path, name: str, output_path: str) -> bool:
    """导出角色卡到独立 JSON 文件。"""
    try:
        card = get_character_card(project_root, name)
        if not card:
            return False
        db_row = get_char_db_row(project_root, name)
        # 合并 JSON + DB 数据
        export = dict(card)
        if db_row:
            for f in ["role", "identity", "ability", "relationship",
                       "arc", "motivation", "alias", "tags"]:
                v = db_row.get(f, "")
                if v:
                    export[f] = v
        Path(output_path).write_text(json.dumps(export, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        return True
    except Exception:
        return False


def import_char_card(project_root: Path, input_path: str) -> bool:
    """从 JSON 文件导入角色卡。"""
    try:
        data = json.loads(Path(input_path).read_text(encoding="utf-8"))
        name = data.pop("name", "")
        if not name:
            return False
        # 写入 JSON 卡
        card = {"name": name}
        for group in ["voice", "personality", "behavior"]:
            card[group] = data.pop(group, {})
        ok = save_character_card(project_root, name, card)
        if not ok:
            return False
        # 写入 DB 字段
        _ensure_char_db_row(project_root, name)
        for f in ["alias", "role", "identity", "ability", "relationship",
                   "arc", "motivation", "tags", "description"]:
            v = data.pop(f, None) if data else None
            if v:
                save_char_db_field(project_root, name, f, str(v))
        return True
    except Exception:
        return False


def extract_dialogue_lines(text: str) -> list[dict]:
    """从文本中提取对话行及其上下文."""
    lines = []
    # 匹配引号内对话（含零引号写法中的人物说）
    for m in re.finditer(r'([\u4e00-\u9fff]{2,6}(?:说|问|答|道|喊|叫|骂|嘀咕|提醒|解释|承认|补充|打断))[：:，,。.]?\s*(.{2,60}?)(?=[，。。！？\n]|$)', text):
        speaker = m.group(1).rstrip("：:,，。.")
        content = m.group(2).strip()
        if len(content) >= 4:
            lines.append({"speaker": speaker, "content": content})
    return lines


def calc_sentence_stats(text: str) -> dict:
    """计算句长统计."""
    sentences = re.split(r'[。！？\n]+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 3]
    if not sentences:
        return {"avg": 0, "std": 0, "short_ratio": 0, "long_ratio": 0, "count": 0}
    lengths = [len(s) for s in sentences]
    avg = sum(lengths) / len(lengths)
    variance = sum((l - avg) ** 2 for l in lengths) / len(lengths)
    std = variance ** 0.5
    short_count = sum(1 for l in lengths if l <= 8)
    long_count = sum(1 for l in lengths if l >= 40)
    return {
        "avg": round(avg, 1),
        "std": round(std, 1),
        "short_ratio": round(short_count / len(lengths), 3),
        "long_ratio": round(long_count / len(lengths), 3),
        "count": len(lengths),
    }


def run_voice_diversity_check(content: str, chapter_no: int,
                               project_root: Path) -> dict:
    """主检测入口：对比当前章节对话与声纹卡."""
    cards = list_voice_cards(project_root)
    findings = []

    if not cards:
        return {
            "guard": "voice_diversity_guard",
            "status": "PASS",
            "score": 100,
            "findings": [{"level": "INFO", "message": "暂无声纹卡，跳过检测"}],
            "chapter_no": chapter_no,
        }

    dialogues = extract_dialogue_lines(content)
    if not dialogues:
        return {
            "guard": "voice_diversity_guard",
            "status": "PASS",
            "score": 100,
            "chapter_no": chapter_no,
            "findings": [],
        }

    # 按说话人分组
    speaker_lines = {}
    for d in dialogues:
        spk = d["speaker"]
        if spk not in speaker_lines:
            speaker_lines[spk] = []
        speaker_lines[spk].append(d["content"])

    # 对每个有声纹卡的角色做检测
    card_map = {c.get("name", ""): c for c in cards}
    for spk, lines in speaker_lines.items():
        card = card_map.get(spk)
        if not card:
            continue

        # 0. 检查方言词覆盖
        dialect = card.get("dialect", "")
        dialect_words = card.get("dialect_words", [])
        if dialect_words:
            found_dialect = sum(1 for w in dialect_words for line in lines if w in line)
            if found_dialect == 0 and len(lines) >= 2:
                findings.append({
                    "level": "WARN",
                    "message": f"角色「{spk}」{dialect}特征丢失——未使用任何方言词",
                    "evidence": f"声纹卡标记方言词: {', '.join(dialect_words[:5])}",
                    "suggestion": f"在 {spk} 的对话中自然嵌入方言词",
                })

        # 1. 检查禁用词
        forbidden = card.get("forbidden_words", [])
        for fw in forbidden:
            for line in lines:
                if fw in line:
                    findings.append({
                        "level": "WARN",
                        "message": f"角色「{spk}」说了不应说的词「{fw}」",
                        "evidence": line[:60],
                        "suggestion": f"声纹卡标记 {spk} 不会说这个词",
                    })

        # 2. 检查常用词覆盖
        common = card.get("common_words", [])
        if common:
            found_common = sum(1 for w in common for line in lines if w in line)
            if found_common == 0 and len(lines) >= 2:
                findings.append({
                    "level": "WARN",
                    "message": f"角色「{spk}」的对话未使用任何习惯用语",
                    "evidence": f"常用词: {', '.join(common[:5])}",
                    "suggestion": f"让 {spk} 在对话中自然使用习惯用语",
                })

        # 3. 检查句长偏好
        pref = card.get("sentence_length_preference", "")
        stats = calc_sentence_stats("。".join(lines))
        if pref == "短句" and stats["avg"] > 20:
            findings.append({
                "level": "WARN",
                "message": f"角色「{spk}」应为短句偏好，实际平均句长 {stats['avg']}",
                "evidence": f"声纹卡标记 {spk} 说短句",
                "suggestion": f"将 {spk} 的对话拆短",
            })
        elif pref == "长句" and stats["avg"] < 12:
            findings.append({
                "level": "WARN",
                "message": f"角色「{spk}」应为长句偏好，实际平均句长 {stats['avg']}",
                "evidence": f"声纹卡标记 {spk} 说长句",
                "suggestion": f"让 {spk} 的对话更完整、更绕",
            })

    # 综合评分
    score = max(0, 100 - len(findings) * 15)
    status = "PASS"
    if len(findings) >= 3:
        status = "WARNING"
    elif len(findings) >= 5:
        status = "FAIL"

    return {
        "guard": "voice_diversity_guard",
        "status": status,
        "score": score,
        "findings": findings,
        "chapter_no": chapter_no,
    }


# ──────────────────────────────────────────────
#  综合角色风格质量检测（v0.7.0+，弹性可配）
# ──────────────────────────────────────────────

# 阈值配置（弹性可调）
STYLE_CHECK_THRESHOLDS = {
    "light": {
        "dialect_density_min": 0.01,    # 最小方言词占比 1%
        "dialect_density_max": 0.25,    # 最大方言词占比 25%
        "catchphrase_min": 0.3,         # 口头禅出现对话占该角色对话比 >= 30%
        "catchphrase_max_flat": 3,      # 无口头禅角色最多容忍 3 次口头禅误判
        "humor_max_serious": 0.15,      # 严肃场景幽默标记密度上限 15%
        "similarity_warn_threshold": 85, # 角色间说话相似度警告线
    },
    "normal": {
        "dialect_density_min": 0.03,
        "dialect_density_max": 0.18,
        "catchphrase_min": 0.5,
        "catchphrase_max_flat": 1,
        "humor_max_serious": 0.10,
        "similarity_warn_threshold": 75,
    },
    "strict": {
        "dialect_density_min": 0.05,
        "dialect_density_max": 0.12,
        "catchphrase_min": 0.7,
        "catchphrase_max_flat": 0,
        "humor_max_serious": 0.05,
        "similarity_warn_threshold": 60,
    },
}


def _detect_serious_scenes(text: str) -> list[tuple[int, int]]:
    """检测严肃场景段落（含 冲突/悲伤/死亡/危机 关键词）。"""
    serious_keywords = ["死", "杀", "伤", "血", "哭", "怒", "恨", "危",
                        "战", "败", "崩", "碎", "裂", "断", "毁", "亡",
                        "暗", "冷", "孤", "绝", "困", "劫", "灾", "难"]
    lines = text.split("\n")
    scenes = []
    for i, line in enumerate(lines):
        if len(line) > 5:
            kw_count = sum(1 for kw in serious_keywords if kw in line)
            if kw_count >= 2:
                scenes.append((i, kw_count))
    return scenes


def run_character_style_check(content: str, chapter_no: int,
                               project_root: Path,
                               intensity: str = "normal") -> dict:
    """弹性角色风格综合检测。

    6 项检测:
    1. 方言密度控制
    2. 人物风格一致
    3. 角色专属口头禅
    4. 严肃场景搞笑禁令
    5. 旁白方言污染
    6. 角色说话相似度

    intensity: light / normal / strict
    """
    thr = STYLE_CHECK_THRESHOLDS.get(intensity, STYLE_CHECK_THRESHOLDS["normal"])
    findings = []
    chars = list_character_cards(project_root)

    # 工具函数：提取对话和旁白
    dialogues = extract_dialogue_lines(content)
    lines = content.split("\n")
    narration_lines = [l for l in lines if not any(
        f"{c.get('name','')}" in l[:10] for c in chars
    )]

    # ──── 1. 方言密度控制 ────
    total_words = len(content)
    for c in chars:
        name = c.get("name", "")
        v = c.get("voice", {})
        dw = v.get("dialect_words", [])
        if not dw:
            continue
        # 计算该角色对话中的方言密度
        char_dialogues = [d for d in dialogues if d["speaker"] == name]
        if not char_dialogues:
            continue
        char_text = " ".join(d["content"] for d in char_dialogues)
        if not char_text:
            continue
        char_len = len(char_text)
        hit_count = sum(char_text.count(w) for w in dw)
        density = hit_count / char_len if char_len > 0 else 0
        if density < thr["dialect_density_min"]:
            findings.append({
                "check": "方言密度",
                "level": "WARN",
                "message": f"「{name}」方言词密度 {density:.1%}，低于阈值 {thr['dialect_density_min']:.0%}",
                "suggestion": f"在 {name} 的对话中增加方言词使用",
            })
        elif density > thr["dialect_density_max"]:
            findings.append({
                "check": "方言密度",
                "level": "WARN",
                "message": f"「{name}」方言词密度 {density:.1%}，高于阈值 {thr['dialect_density_max']:.0%}",
                "suggestion": f"减少 {name} 对话中的方言词密度",
            })

    # ──── 2. 人物风格一致检查 ────
    for c in chars:
        name = c.get("name", "")
        p = c.get("personality", {})
        b = c.get("behavior", {})
        core = p.get("core", "")
        stress = b.get("stress_response", "")
        if not core and not stress:
            continue
        # 简单风格一致性提示
        hints = []
        if core:
            hints.append(f"性格「{core}」")
        if stress:
            hints.append(f"压力反应「{stress}」")
        if hints:
            findings.append({
                "check": "人物风格",
                "level": "INFO",
                "message": f"「{name}」需注意风格一致: {'/'.join(hints)}",
                "suggestion": f"检查本章 {name} 的行为是否匹配其性格设定",
            })

    # ──── 3. 角色专属口头禅 ────
    for c in chars:
        name = c.get("name", "")
        v = c.get("voice", {})
        catchphrase = v.get("catchphrase", "")
        if not catchphrase:
            continue
        char_dialogues = [d for d in dialogues if d["speaker"] == name]
        if not char_dialogues:
            continue
        has_it = any(catchphrase in d["content"] for d in char_dialogues)
        total_d = len(char_dialogues)
        found = sum(1 for d in char_dialogues if catchphrase in d["content"])
        ratio = found / total_d if total_d > 0 else 0
        if ratio < thr["catchphrase_min"]:
            findings.append({
                "check": "口头禅",
                "level": "WARN" if found == 0 else "INFO",
                "message": f"「{name}」口头禅「{catchphrase}」出现 {found}/{total_d} 次 ({ratio:.0%})",
                "suggestion": f"让 {name} 在对话中自然使用" + (f"「{catchphrase}」" if catchphrase else ""),
            })

    # ──── 4. 严肃场景禁止密集搞笑 ────
    serious_scenes = _detect_serious_scenes(content)
    if serious_scenes:
        humor_count = 0
        for c in chars:
            v = c.get("voice", {})
            hs = v.get("humor_style", "")
            if hs:
                humor_count += 1
        # 统计严肃段落中的幽默标记密度
        serious_text = "\n".join(lines[i] for i, _ in serious_scenes[:10])
        total_serious = len(serious_text)
        if total_serious > 100:
            humor_markers = ["笑", "逗", "搞", "乐", "幽默", "玩笑", "调侃", "打趣"]
            humor_hits = sum(serious_text.count(m) for m in humor_markers)
            humor_density = humor_hits / total_serious
            if humor_density > thr["humor_max_serious"]:
                findings.append({
                    "check": "严肃场景",
                    "level": "WARN",
                    "message": f"严肃场景中幽默标记密度 {humor_density:.1%}，超过阈值 {thr['humor_max_serious']:.0%}",
                    "suggestion": "检查严肃段落是否有不合时宜的搞笑内容",
                })

    # ──── 5. 旁白方言污染 ────
    narration_text = "\n".join(narration_lines)
    for c in chars:
        v = c.get("voice", {})
        dw = v.get("dialect_words", [])
        if not dw:
            continue
        for w in dw:
            if len(w) < 2:
                continue  # 单字词跳过，误报太高
            # 整词匹配而非子串匹配
            import re as _re
            pattern = _re.compile(rf'(?<!\w){_re.escape(w)}(?!\w)')
            if pattern.search(narration_text):
                findings.append({
                    "check": "旁白污染",
                    "level": "INFO",
                    "message": f"方言词「{w}」出现在旁白中（角色「{c.get('name','')}」的方言词）",
                    "suggestion": f"方言词应仅出现在对话中",
                })
                break

    # ──── 6. 角色说话相似度检测 ────
    if len(chars) >= 2:
        speaker_texts = {}
        for d in dialogues:
            spk = d["speaker"]
            if spk not in speaker_texts:
                speaker_texts[spk] = []
            speaker_texts[spk].append(d["content"])
        speakers = list(speaker_texts.keys())
        for i in range(len(speakers)):
            for j in range(i + 1, len(speakers)):
                a, b = speakers[i], speakers[j]
                ta = " ".join(speaker_texts[a])
                tb = " ".join(speaker_texts[b])
                if len(ta) < 10 or len(tb) < 10:
                    continue
                # 简单用词重叠度（可作为相似度指标）
                words_a = set(ta)
                words_b = set(tb)
                common = words_a & words_b
                similarity = len(common) / max(len(words_a | words_b), 1) * 100
                if similarity > thr["similarity_warn_threshold"]:
                    findings.append({
                        "check": "说话相似度",
                        "level": "WARN",
                        "message": f"「{a}」与「{b}」用词重叠 {similarity:.0f}%，超过阈值 {thr['similarity_warn_threshold']}%",
                        "suggestion": f"差异化 {a} 和 {b} 的用词习惯",
                    })

    # 评分
    warn_count = sum(1 for f in findings if f["level"] == "WARN")
    score = max(0, 100 - warn_count * 12)
    if warn_count == 0:
        status = "PASS"
    elif warn_count <= 3:
        status = "WARNING"
    else:
        status = "FAIL"

    return {
        "guard": "character_style_check",
        "version": "v0.7.0",
        "status": status,
        "score": score,
        "findings": findings,
        "chapter_no": chapter_no,
        "intensity": intensity,
        "checks_run": 6,
    }
