#!/usr/bin/env python3
"""src/cli/commands_character.py — 角色综合管理 v0.6.6

管理角色的声纹、性格、做事风格三个维度。

命令:
  python novel.py character list                   列出所有角色卡
  python novel.py character show <角色名>           查看完整角色卡
  python novel.py character create <角色名>         创建默认角色卡
  python novel.py character delete <角色名>         删除角色卡
  python novel.py character edit <角色名> <字段> <值>  编辑指定字段
  python novel.py character outline-check          从大纲检查角色卡状态
  python novel.py character outline-check --create  检查 + 自动创建缺失卡
"""

import sys
import json
import re
from pathlib import Path
from src.cli.shared import PROJECT_ROOT, SCRIPTS_DIR
from src.cli.commands_voice import _resolve_chapter_path
from src.guards.human_texture.voice_diversity_guard import (
    get_character_card, list_character_cards, save_character_card,
    delete_voice_card,
    get_active_voice_card_set, set_active_voice_card_set, list_voice_card_sets,
    get_char_db_row, save_char_db_field, delete_char_db_row, _ensure_char_db_row,
    get_focus_state, set_focus_state, FOCUS_STATE_CHOICES,
    set_relation, delete_relation, list_relations, get_relations_for,
    export_char_card, import_char_card,
    VOICE_CARD_FIELDS, PERSONALITY_FIELDS, BEHAVIOR_FIELDS, STORY_FIELDS, PERSONALITY_CHOICES,
    DB_CHAR_FIELDS, DB_CHAR_FIELD_NAMES_EXT,
    MENTAL_STATE_CATEGORIES,
)
from src.guards.human_texture.mental_state_crud import (
    get_mental_state, save_mental_state, list_mental_states,
)


def _normalize_mental_category(cat: str) -> str:
    """规范化精神状态类别名：接受半角括号作为全角括号的别名。"""
    cat = cat.replace("(", "（").replace(")", "）")
    return cat


def _new_empty_card(name: str) -> dict:
    """创建默认空白角色卡."""
    return {
        "name": name,
        "voice": {k: "" for k in VOICE_CARD_FIELDS},
        "personality": {k: "" for k in PERSONALITY_FIELDS},
        "behavior": {k: ([] if k == "habits" else "") for k in BEHAVIOR_FIELDS},
        "story": {k: "" for k in STORY_FIELDS},
    }


def _get_outline_content() -> tuple[str, str, int]:
    """获取当前活跃大纲内容，返回 (title, content, chapter_count)."""
    mgr = __import__("scripts.outline.outline_manager", fromlist=["OutlineManager"])
    OM = getattr(mgr, "OutlineManager")
    om = OM(PROJECT_ROOT)
    outline = om.current_outline()
    if not outline:
        return ("", "", 0)
    content = outline.get("content", "")
    title = outline.get("title", "未命名大纲")
    cc = outline.get("chapter_count", 0)
    return (title, content, cc)


def _extract_chinese_names(text: str) -> set:
    """从文本中提取中文人名."""
    surnames_str = ("李王张刘陈杨赵黄周吴徐孙马胡朱郭何林高罗"
                    "郑梁谢宋唐许邓韩冯曹彭曾肖田董潘袁蔡蒋余"
                    "于杜叶程苏魏吕丁任卢姚沈姜崔钟谭陆汪范金"
                    "石廖贾夏韦傅方白邹孟熊秦邱江尹薛阎段雷侯"
                    "龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤"
                    "鲁萧齐魂")
    surnames = set(surnames_str)
    reliable_names = set()
    heuristic_names = set()

    # 方法1a：角色字段后提取（带冒号）
    for pattern in [r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[：:]\s*([^\n，。]{2,4})',
                    r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[是为叫作叫做称呼]\s*([^\n，。]{2,4})']:
        for m in re.finditer(pattern, text):
            name = m.group(1).strip()
            if 2 <= len(name) <= 4:
                reliable_names.add(name)

    # 方法1b：男主林观澜 / 女主沈青霜 / 师尊顾长庚（角色名紧接姓名）
    for m in re.finditer(r'(?:男主|女主|师尊|反派|前世女友|东北|山东|山东人|核心人物|讲理人)([\u4e00-\u9fff]{2,4})(?:[：:，，\n])', text):
        name = m.group(1).strip()
        if name[0] in surnames and 2 <= len(name) <= 4:
            reliable_names.add(name)

    # 方法1c：编号开头 + 姓名 + 冒号（如 1. 鲁砚山：）
    for m in re.finditer(r'^\s*\d+[.、]\s*([\u4e00-\u9fff]{2,4})[：:]', text, re.MULTILINE):
        name = m.group(1).strip()
        if name[-1] not in "的写了发现说看和与在把被将为对来去出进到从以":
            if 2 <= len(name) <= 4:
                # 只有首字是常见姓或者名字包含已有姓氏才加入
                if name[0] in surnames or any(s in name for s in surnames):
                    reliable_names.add(name)

    # 方法1d：行首姓名+冒号（无编号），如 罗千钧： 或 天道尸骸：
    for m in re.finditer(r'^([\u4e00-\u9fff]{2,4})[：:]\s', text, re.MULTILINE):
        name = m.group(1).strip()
        if name[0] in surnames and 2 <= len(name) <= 4:
            reliable_names.add(name)
    # 1e: 4字名在行首被 / 或空格分隔的情况，如 "天道尸骸 / 齐岳老祖："
    for m in re.finditer(r'^([\u4e00-\u9fff]{4})\s*[/／]\s*([\u4e00-\u9fff]{2,4})[：:]', text, re.MULTILINE):
        for g in [m.group(1), m.group(2)]:
            if g[0] in surnames and 2 <= len(g) <= 4:
                reliable_names.add(g)

    # 方法2：姓氏启发式 — 仅提取 2 字名
    _punct_chars = set('，。！？、；：''（）《》…— \t,./!?;:()[]{}"')
    _bad_endings = {"场", "上", "下", "里", "前", "后", "中", "的", "了",
                    "和", "与", "在", "把", "被", "将", "对", "为",
                    "都", "也", "还", "就", "已", "能", "会", "可",
                    "来", "去", "出", "进", "到", "从", "以"}
    _COMMON_COMPOUNDS = {
        "严禁", "严肃", "严重", "严格",
        "过程", "工程", "程度", "程序", "章程", "课程",
        "关于", "等于", "至于", "由于", "位于", "对于", "属于", "终于",
        "马上", "马路",
        "王国", "帝王", "霸王",
        "龙王", "巨龙", "恐龙", "神龙",
        "森林", "树林", "丛林", "园林", "密林",
        "资金", "金属", "现金", "黄金",
        "石头", "宝石", "钻石", "化石", "岩石",
        "方法", "方式", "方案", "方向", "方面",
        "高度", "高级", "高大", "高尚",
        "周围", "周期", "周年",
        "黄色", "黄昏",
        "江湖", "江山",
        "明白", "黑白", "洁白",
        "历史", "史书",
        "毛病", "毛发",
        "万物", "万事", "万一",
        "武器", "武功", "武术",
        "雷霆", "雷电",
        "段落", "手段", "阶段",
        "任何", "如何",
        "感谢", "谢谢",
        "苏醒", "复苏",
        "沉思", "沉重",
        "范围", "范例",
        "清楚", "清晰", "清醒", "清理",
        "叶子", "树叶",
        "白不", "白保", "白死", "白山", "孙白",
        "于普", "于台", "于复", "于天", "于明", "于罗",
        "段人", "段必", "段温", "段讲",
        "程杀", "程问",
        "许只", "许男", "林哥", "林观",
        "罗千", "顾长", "沈青", "许知", "许铁", "赵二",
        "鲁砚", "齐岳", "萧无",
        "魂是", "魂频",
        "金丹", "雷法", "雷火",
        "高光", "高兴", "高压", "高维",
        "莫急", "石灰", "方程", "方言", "任务",
        "严禁", "方言轻量", "鲁三", "鲁哥",
    }
    for i, ch in enumerate(text):
        if ch in surnames and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt not in _punct_chars:
                candidate2 = text[i:i + 2]
                if candidate2[1] not in _bad_endings and candidate2 not in _COMMON_COMPOUNDS:
                    heuristic_names.add(candidate2)

    # 合并
    result = set(reliable_names)
    for hn in heuristic_names:
        hn = hn.strip()
        if any(hn in rn or rn in hn for rn in reliable_names):
            continue
        _stop = {"时候", "地方", "这里", "那里", "这边", "那边", "怎么", "什么",
                 "没有", "已经", "可以", "需要", "知道", "看见", "告诉", "开始",
                 "继续", "回到", "来到", "走出", "进入", "拿起", "放下"}
        if hn in _stop:
            continue
        if text.count(hn) < 2:
            continue
        result.add(hn)

    # 后处理：剔除2字碎片（如果3/4字名已存在）
    final = set()
    for n in sorted(result, key=len, reverse=True):
        if len(n) == 2 and any(n in longer for longer in final):
            continue
        if text.count(n) >= 2 or n in reliable_names:
            final.add(n)

    return {n for n in final if 2 <= len(n) <= 4}

def _get_db_characters() -> list[dict]:
    """从当前 slot 的 characters 表获取所有已注册角色."""
    try:
        ws_dir = PROJECT_ROOT / "workspace"
        reg_file = ws_dir / "registry.json"
        if not reg_file.exists():
            return []
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        if not active:
            return []
        db_path = ws_dir / active / "novel.db"
        if not db_path.exists():
            return []
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.execute("SELECT name, alias, role, identity FROM characters WHERE status='active'")
        rows = cur.fetchall()
        conn.close()
        result = []
        for r in rows:
            char = {"name": r[0]}
            if r[1]:
                char["alias"] = r[1]
            if r[2]:
                char["role"] = r[2]
            if r[3]:
                char["identity"] = r[3]
            result.append(char)
        return result
    except Exception:
        return []


# ── 展示工具 ──

def _render_field(field: str, val) -> str:
    """将字段值渲染为可读字符串."""
    if isinstance(val, list):
        if not val:
            return "无"
        return ", ".join(val[:5])
    if isinstance(val, dict):
        if not val:
            return "无"
        return json.dumps(val, ensure_ascii=False)[:40]
    return str(val) if val else "无"


def _print_char_table(cards: list[dict]):
    """打印角色卡表格."""
    if not cards:
        print("  当前小说无角色卡")
        return
    print(f"  角色卡 ({len(cards)} 个):")
    print(f"  {'角色':8s} {'性格':6s} {'决策':8s} {'社交':6s} {'方言':6s}")
    print(f"  {'-'*8} {'-'*6} {'-'*8} {'-'*6} {'-'*6}")
    for c in cards:
        name = c.get("name", "?")
        p = c.get("personality", {})
        b = c.get("behavior", {})
        v = c.get("voice", {})
        core = p.get("core", "") or "无"
        decision = p.get("decision_style", "") or "无"
        social = b.get("social_style", "") or "无"
        dialect = v.get("dialect", "") or "无"
        print(f"  {name:8s} {core:6s} {decision:8s} {social:6s} {dialect:6s}")


# ── 子命令处理 ──

def _char_list():
    """列出所有角色卡."""
    cards = list_character_cards(PROJECT_ROOT)
    if not cards:
        cards = _get_db_characters()
    _print_char_table(cards)
    print()
    current_set = get_active_voice_card_set(PROJECT_ROOT)
    print(f"  卡组: {current_set}")
    print(f"  详情: python novel.py character show <角色名>")


def _char_show(name: str):
    """显示完整角色卡（JSON 角色卡 + DB 数据合并）."""
    card = get_character_card(PROJECT_ROOT, name)
    # 获取 DB 行
    db_row = get_char_db_row(PROJECT_ROOT, name)
    if not card:
        if db_row:
            card = {"name": db_row.get("name", name), "personality": {}, "behavior": {}}
        else:
            print(f"  未找到角色「{name}」")
            return

    print(f"  ╔══ 角色卡 ── {name} ═══")
    print()

    # ── 身份 ──
    role_v = db_row.get("role", "") if db_row else ""
    identity_v = db_row.get("identity", "") if db_row else ""
    ability_v = db_row.get("ability", "") if db_row else ""
    alias_v = db_row.get("alias", "") if db_row else ""
    has_identity = any([role_v, identity_v, ability_v])

    # ── 性格 ──
    personality = card.get("personality", {})
    desc_v = db_row.get("personality_info", "") if db_row else ""
    has_personality = any(personality.get(f) for f in PERSONALITY_FIELDS) or bool(desc_v)

    # ── 做事风格 ──
    behavior = card.get("behavior", {})
    has_behavior = any(behavior.get(f) for f in BEHAVIOR_FIELDS if behavior.get(f))

    # ── 叙事层 ──
    story = card.get("story", {})
    has_story = any(story.get(f) for f in STORY_FIELDS if story.get(f))

    # ── 精神状态（从独立文件读取）──
    mental = get_mental_state(PROJECT_ROOT, name)
    has_mental = bool(mental and any(v is not None for v in mental.values()))

    # ── 声纹 ──
    voice = card.get("voice", {})
    has_voice = any(voice.get(f) for f in VOICE_CARD_FIELDS)

    # ── 关系 ──
    rel_v = db_row.get("relationship", "") if db_row else ""
    has_rel = bool(rel_v)

    # ── 成长弧 ──
    arc_v = db_row.get("arc", "") if db_row else ""
    mot_v = db_row.get("motivation", "") if db_row else ""
    has_arc = bool(arc_v or mot_v)

    # ── 叙事层 ──
    has_story = any(story.get(f) for f in STORY_FIELDS if story.get(f))

    # ── 元数据 ──
    tags_v = db_row.get("tags", "") if db_row else ""
    has_meta = bool(alias_v or tags_v)

    # 计算所有可见段
    sections = []
    if has_identity:
        sections.append("identity")
    if has_personality:
        sections.append("personality")
    if has_behavior:
        sections.append("behavior")
    if has_mental:
        sections.append("mental_state")
    if has_voice:
        sections.append("voice")
    if has_story:
        sections.append("story")
    if has_rel:
        sections.append("relationship")
    if has_arc:
        sections.append("arc")
    if has_meta:
        sections.append("meta")

    if not sections:
        print(f"  └─ (空白角色卡)")
        print()
        print(f"  ╚═══")
        print()
        print(f"  编辑: python novel.py character edit {name} <字段> <值>")
        print(f"  例如: python novel.py character edit {name} core 沉稳")
        print(f"        python novel.py character edit {name} identity 外门弟子")
        print(f"        python novel.py character edit {name} relationship 苏晚晴:知己")
        return

    idx = 0
    for sec in sections:
        is_first = (idx == 0)
        is_last = (idx == len(sections) - 1)
        prefix = "  ┌─ " if is_first else ("  └─ " if is_last else "  ├─ ")
        idx += 1

        if sec == "identity":
            print(f"{prefix}【身份】")
            if role_v:
                print(f"  │  定位: {role_v}")
            if identity_v:
                print(f"  │  身份: {identity_v}")
            if ability_v:
                print(f"  │  能力: {ability_v}")

        elif sec == "personality":
            print(f"{prefix}【性格】")
            for f in PERSONALITY_FIELDS:
                val = personality.get(f, "")
                if val:
                    print(f"  │  {f}: {val}")
            if desc_v:
                print(f"  │  描述: {desc_v}")

        elif sec == "behavior":
            print(f"{prefix}【做事风格】")
            for f in BEHAVIOR_FIELDS:
                val = behavior.get(f, "")
                if isinstance(val, list):
                    if val:
                        print(f"  │  {f}: {', '.join(val)}")
                elif val:
                    print(f"  │  {f}: {val}")

        elif sec == "story":
            story = card.get("story", {})
            print(f"{prefix}【叙事层】")
            has_story = False
            for f in STORY_FIELDS:
                val = story.get(f, "")
                if val:
                    has_story = True
                    label = {"motivation": "核心动机", "fatal_flaw": "致命缺陷",
                             "secret": "秘密", "trauma": "关键创伤",
                             "goal_short": "短期目标", "goal_long": "长期目标",
                             "ability": "特长", "weakness": "短板",
                             "arc_intended": "预定弧线", "arc_current": "弧线当前"}.get(f, f)
                    print(f"  │  {label}: {val}")
            if not has_story:
                print(f"  │  (未设置)")

        elif sec == "mental_state":
            print(f"{prefix}【精神状态】")
            for cat in MENTAL_STATE_CATEGORIES:
                data = mental.get(cat, None)
                if data is None:
                    continue
                sev = data.get("severity", 0)
                onset = data.get("onset", "") or ""
                bar = "█" * sev + "░" * (5 - sev)
                print(f"  │  {cat} ({sev}/5 {bar})")
                if onset:
                    print(f"  │    {onset}")

        elif sec == "voice":
            print(f"{prefix}【声纹】")
            for f in VOICE_CARD_FIELDS:
                val = voice.get(f, "")
                if val:
                    print(f"  │  {f}: {_render_field(f, val)}")

        elif sec == "story":
            print(f"{prefix}【叙事层】")
            labels = {"motivation": "核心动机", "fatal_flaw": "致命缺陷",
                      "secret": "秘密", "trauma": "关键创伤",
                      "goal_short": "短期目标", "goal_long": "长期目标",
                      "ability": "特长", "weakness": "短板",
                      "arc_intended": "预定弧线", "arc_current": "弧线当前"}
            for f in STORY_FIELDS:
                val = story.get(f, "")
                if val:
                    label = labels.get(f, f)
                    val_str = val[:60] + "..." if len(val) > 60 else val
                    print(f"  │  {label}: {val_str}")

        elif sec == "relationship":
            print(f"{prefix}【关系】")
            for pair in rel_v.split(","):
                pair = pair.strip()
                if ":" in pair:
                    k, v = pair.split(":", 1)
                    print(f"  │  {k.strip()}: {v.strip()}")
                else:
                    print(f"  │  {pair}")

        elif sec == "arc":
            print(f"{prefix}【成长弧】")
            if arc_v:
                print(f"  │  弧线: {arc_v}")
            if mot_v:
                print(f"  │  动机: {mot_v}")

        elif sec == "meta":
            print(f"{prefix}【元数据】")
            if alias_v:
                print(f"     别名: {alias_v}")
            if tags_v:
                print(f"     标签: {tags_v}")

    print()
    print(f"  ╚═══")
    print()
    print(f"  编辑: python novel.py character edit {name} <字段> <值>")
    print(f"  例如: python novel.py character edit {name} core 沉稳")
    print(f"        python novel.py character edit {name} identity 外门弟子")
    print(f"        python novel.py character edit {name} relationship 苏晚晴:知己")


def _char_create(name: str):
    """创建默认角色卡（JSON + DB 同步创建）."""
    card = get_character_card(PROJECT_ROOT, name)
    if card:
        print(f"  角色「{name}」已存在，将被覆盖")
    card = _new_empty_card(name)
    ok = save_character_card(PROJECT_ROOT, name, card)
    # 同时确保 DB 行存在
    _ensure_char_db_row(PROJECT_ROOT, name)
    if ok:
        print(f"  ✅ 已创建角色卡「{name}」")
        print(f"  查看: python novel.py character show {name}")
        print(f"  编辑: python novel.py character edit {name} <字段> <值>")
    else:
        print(f"  ❌ 创建失败（无法确定当前 slot）")


def _char_delete(name: str):
    """删除角色卡（JSON + DB 同步删除）."""
    card = get_character_card(PROJECT_ROOT, name)
    if not card:
        print(f"  未找到角色「{name}」")
        return
    ok = delete_voice_card(PROJECT_ROOT, name)
    delete_char_db_row(PROJECT_ROOT, name)  # 标记 DB 行删除
    if ok:
        print(f"  ✅ 已删除角色卡「{name}」")
    else:
        print(f"  ❌ 删除失败")


def _char_edit(name: str, field: str, value: str):
    """编辑角色卡指定字段（自动路由到 JSON 或 DB）."""
    card = get_character_card(PROJECT_ROOT, name)
    if not card:
        print(f"  未找到角色「{name}」")
        print(f"  先创建: python novel.py character create {name}")
        return

    # 检查是否为 DB 字段
    if field in DB_CHAR_FIELD_NAMES_EXT:
        ok = save_char_db_field(PROJECT_ROOT, name, field, value)
        if ok:
            print(f"  ✅ 已更新「{name}」的 {field} = {value}")
        else:
            print(f"  ❌ 保存失败（DB 不可用）")
        return

    # 解析字段路径: core, voice.dialect, personality.decision_style 等
    parts = field.split(".")
    if len(parts) == 1:
        # 自动匹配所属分组
        sub_field = parts[0]
        found = False
        for group_name, group_fields in [("voice", VOICE_CARD_FIELDS),
                                          ("personality", PERSONALITY_FIELDS),
                                          ("behavior", BEHAVIOR_FIELDS),
                                          ("story", STORY_FIELDS)]:
            if sub_field in group_fields:
                if sub_field == "habits":
                    card[group_name][sub_field] = [v.strip() for v in value.split(",") if v.strip()]
                else:
                    card[group_name][sub_field] = value
                found = True
                break
        if not found:
            print(f"  ❌ 未知字段「{field}」")
            all_fields = VOICE_CARD_FIELDS + PERSONALITY_FIELDS + BEHAVIOR_FIELDS + DB_CHAR_FIELD_NAMES_EXT
            print(f"  可用字段: {' '.join(all_fields)}")
            return
    elif len(parts) == 2:
        group, sub_field = parts
        if group not in card or sub_field not in card[group]:
            print(f"  ❌ 未知字段路径「{field}」")
            return
        if sub_field == "habits":
            card[group][sub_field] = [v.strip() for v in value.split(",") if v.strip()]
        else:
            card[group][sub_field] = value
    else:
        print(f"  ❌ 字段路径格式不正确: {field}")
        return

    ok = save_character_card(PROJECT_ROOT, name, card)
    if ok:
        print(f"  ✅ 已更新「{name}」的 {field} = {value}")
    else:
        print(f"  ❌ 保存失败")


def _char_outline_check(create_missing: bool = False):
    """从大纲检查所有角色的角色卡状态."""
    title, content, ch_count = _get_outline_content()
    if not title:
        print("  ⛔ 当前没有激活的大纲")
        return

    print(f"  📋 大纲: {title} ({ch_count} 章)")
    print()

    # 提取角色名
    extracted_names = _extract_chinese_names(content)
    db_chars = _get_db_characters()
    db_names = {c["name"] for c in db_chars}
    for c in db_chars:
        alias = c.get("alias", "")
        if alias:
            for a in alias.split(","):
                a = a.strip()
                if a:
                    db_names.add(a)

    all_chars = extracted_names | db_names
    if not all_chars:
        print("  ⚠️  大纲中未检测到角色名")
        return

    # 获取现有角色卡
    cards = list_character_cards(PROJECT_ROOT)
    card_map = {c.get("name", ""): c for c in cards}
    card_set = set(card_map.keys())

    has_card = sorted(all_chars & card_set)
    missing = sorted(all_chars - card_set)

    print(f"  🎭 检测到 {len(all_chars)} 个角色:")
    print()

    for name in sorted(all_chars):
        source = []
        if name in extracted_names:
            source.append("大纲")
        if name in db_names:
            source.append("DB")
        src_tag = f"[{'/'.join(source)}]"

        if name in card_set:
            cc = card_map[name]
            p = cc.get("personality", {})
            b = cc.get("behavior", {})
            core = p.get("core", "") or "未设"
            soc = b.get("social_style", "") or "未设"
            has_personality = bool(p.get("core") or p.get("decision_style"))
            has_behavior = bool(b.get("social_style") or b.get("stress_response"))
            tags = []
            if has_personality:
                tags.append("性格")
            if has_behavior:
                tags.append("做事")
            tag_str = f"({'/'.join(tags)})" if tags else "(仅声纹)"
            print(f"    ✅ {name:8s} {src_tag:12s} 性格:{core:6s} 社交:{soc:6s} {tag_str}")
        else:
            print(f"    ❌ {name:8s} {src_tag:12s} 无角色卡")

    print()

    if missing:
        print(f"  ⚠️  {len(missing)} 个角色尚未创建:")
        for name in missing:
            print(f"     python novel.py character create {name}")
        print()

        if create_missing:
            created = 0
            for name in missing:
                ok = save_character_card(PROJECT_ROOT, name, _new_empty_card(name))
                if ok:
                    created += 1
            print(f"  ✅ 已自动创建 {created}/{len(missing)} 个角色的默认卡")
            # 重新计算
            cards = list_character_cards(PROJECT_ROOT)
            card_map = {c.get("name", ""): c for c in cards}
            card_set = set(card_map.keys())
            has_card = sorted(all_chars & card_set)
            missing = sorted(all_chars - card_set)
        else:
            print(f"  💡 加 --create 自动创建默认角色卡")
    else:
        print("  ✅ 所有角色均已配置角色卡")

    extra = db_names - extracted_names
    if extra:
        print()
        print(f"  📌 DB 中有但大纲中未出现的角色（可能已过时）:")
        for name in sorted(extra):
            print(f"     {name}")

    print()
    current_set = get_active_voice_card_set(PROJECT_ROOT)
    print(f"  📁 当前卡组: {current_set}")
    cov = round(len(has_card) / len(all_chars) * 100) if all_chars else 0
    print(f"  📊 角色卡覆盖率: {len(has_card)}/{len(all_chars)} ({cov}%)")


# ── 关系管理 ──

def _char_relate(a: str, b: str, rel_type: str):
    ok = set_relation(PROJECT_ROOT, a, b, rel_type)
    if ok:
        print(f"  ✅ {a} — {b} : {rel_type}")
    else:
        print(f"  ❌ 设置失败（DB 不可用）")


def _char_unrelate(a: str, b: str):
    ok = delete_relation(PROJECT_ROOT, a, b)
    if ok:
        print(f"  ✅ 已删除 {a} — {b} 的关系")
    else:
        print(f"  ❌ 未找到该关系")


def _char_relation_graph():
    rels = list_relations(PROJECT_ROOT)
    if not rels:
        print("  当前小说无角色关系数据")
        print("  设置: python novel.py character relate <角色A> <角色B> <关系>")
        return
    chars = set()
    for r in rels:
        chars.add(r["char_a"])
        chars.add(r["char_b"])
    print(f"  📊 角色关系图谱（{len(rels)} 条关系，{len(chars)} 个角色）")
    print()
    print(f"  {'角色':8s} {'关系数':6s} {'关系列表'}")
    print(f"  {'-'*8} {'-'*6} {'-'*40}")
    for c in sorted(chars):
        my_rels = [r for r in rels if r["char_a"] == c or r["char_b"] == c]
        other = [(r["char_b"] if r["char_a"] == c else r["char_a"], r["type"]) for r in my_rels]
        parts = [f"{o[0]}({o[1]})" for o in other]
        print(f"  {c:8s} {len(my_rels):6d} {' '.join(parts)}")


# ── 导入导出 ──

def _char_export(name: str, output_path: str = ""):
    card = get_character_card(PROJECT_ROOT, name)
    if not card:
        print(f"  未找到角色「{name}」")
        return
    if not output_path:
        output_path = f"{name}.json"
    ok = export_char_card(PROJECT_ROOT, name, output_path)
    if ok:
        print(f"  ✅ 已导出「{name}」到 {output_path}")
    else:
        print(f"  ❌ 导出失败")


def _char_import(input_path: str):
    if not Path(input_path).exists():
        print(f"  ❌ 文件不存在: {input_path}")
        return
    ok = import_char_card(PROJECT_ROOT, input_path)
    if ok:
        print(f"  ✅ 已导入角色卡: {input_path}")
    else:
        print(f"  ❌ 导入失败（格式不正确或角色名缺失）")


# ── 聚焦状态 ──

def _char_focus(name: str, state: str):
    if state not in FOCUS_STATE_CHOICES:
        print(f"  ❌ 状态必须是 {'/'.join(FOCUS_STATE_CHOICES)}")
        return
    ok = set_focus_state(PROJECT_ROOT, name, state)
    if ok:
        print(f"  ✅ 「{name}」聚焦状态 → {state}")
    else:
        print(f"  ❌ 设置失败")


# ── 弧线进度检查 ──

def _char_arc_check():
    import sqlite3
    ws_dir = PROJECT_ROOT / "workspace"
    reg_f = ws_dir / "registry.json"
    if not reg_f.exists():
        print("  没有活跃工作区")
        return
    reg = json.loads(reg_f.read_text(encoding="utf-8"))
    active = reg.get("active_slot", "")
    if not active:
        print("  没有活跃 slot")
        return
    slot_db = ws_dir / active / "novel.db"
    if not slot_db.exists():
        print("  数据库不存在")
        return
    conn = sqlite3.connect(str(slot_db))
    ch_count = conn.execute("SELECT COUNT(*) FROM chapters WHERE status='ingested'").fetchone()[0]
    chars = conn.execute(
        "SELECT name, arc, motivation, focus_state FROM characters "
        "WHERE status='active' AND (arc != '' OR motivation != '')"
    ).fetchall()
    conn.close()
    if not chars:
        print("  没有角色设置弧线或动机")
        return
    print(f"  📊 弧线进度检查（已写 {ch_count} 章）")
    for c in chars:
        name = c[0]; arc = c[1] or ""; mot = c[2] or ""; foc = c[3] or "活跃"
        progress = "✓" if arc else "—"
        mot_ok = "✓" if mot else "—"
        ftag = f" [{foc}]" if foc != "活跃" else ""
        arc_short = (arc[:40] + "…") if len(arc) > 40 else arc
        mot_short = (mot[:30] + "…") if len(mot) > 30 else mot
        print(f"  {name:8s} 弧:{progress} 动机:{mot_ok}{ftag}")
        if arc: print(f"         弧线: {arc_short}")
        if mot: print(f"         动机: {mot_short}")


# ── 故事合同同步 ──

def _char_sync_story():
    cards = list_character_cards(PROJECT_ROOT)
    if not cards:
        print("  当前小说无角色卡")
        return
    ws_dir = PROJECT_ROOT / "workspace"
    reg = json.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
    active = reg.get("active_slot", "")
    story_dir = (ws_dir / active / ".story") if active else (PROJECT_ROOT / ".story")
    mem_dir = story_dir / "memory"
    if not mem_dir.exists():
        print(f"  ⚠️  故事合同未初始化，请先运行: python novel.py story init")
        return
    char_list = []
    for c in cards:
        name = c.get("name", "")
        db_row = get_char_db_row(PROJECT_ROOT, name)
        entry = {"name": name}
        p = c.get("personality", {})
        if p.get("core"):
            entry["personality"] = p["core"]
        if db_row:
            for f in ["role", "identity", "ability", "relationship",
                       "arc", "motivation", "alias"]:
                v = db_row.get(f, "")
                if v:
                    entry[f] = v
        char_list.append(entry)
    char_file = mem_dir / "characters.json"
    char_file.write_text(json.dumps(char_list, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    print(f"  ✅ 已同步 {len(char_list)} 个角色到故事合同")
    print(f"     路径: {char_file}")


# ── 综合风格检查 ──

def _char_style_check(chapter_no: str, intensity: str = "normal"):
    """运行综合角色风格检测（6项弹性检查）。"""
    # 找章节文件
    ch_path = _resolve_chapter_path(chapter_no)
    if not ch_path:
        print(f"  ❌ 找不到第{chapter_no}章文件")
        return
    content = Path(ch_path).read_text(encoding="utf-8")
    from src.guards.human_texture.voice_diversity_guard import run_character_style_check
    result = run_character_style_check(content, int(chapter_no), PROJECT_ROOT, intensity)
    print(f"  📊 角色风格检测 — 第{chapter_no}章 [{intensity}]")
    print(f"     评分: {result['score']}/100 | 状态: {result['status']}")
    print()
    for f in result.get("findings", []):
        lvl = f.get("level", "INFO")
        chk = f.get("check", "")
        msg = f.get("message", "")
        sug = f.get("suggestion", "")
        icon = {"WARN": "⚠️ ", "INFO": "💡", "FAIL": "❌ "}.get(lvl, "   ")
        print(f"  {icon}[{chk}] {msg}")
        if sug:
            print(f"         → {sug}")

def _char_chapters(name: str):
    """查角色在哪些章节出场了。"""
    import sqlite3
    ws_dir = PROJECT_ROOT / "workspace"
    reg_f = ws_dir / "registry.json"
    if not reg_f.exists():
        print("  没有活跃工作区")
        return
    reg = json.loads(reg_f.read_text(encoding="utf-8"))
    active = reg.get("active_slot", "")
    if not active:
        return
    slot_db = ws_dir / active / "novel.db"
    if not slot_db.exists():
        print("  数据库不存在")
        return
    conn = sqlite3.connect(str(slot_db))
    results = []

    # 1. 从 chapter_plans.character_focus 查
    focus_rows = conn.execute(
        "SELECT DISTINCT chapter_no FROM chapter_plans "
        "WHERE character_focus LIKE ? ORDER BY chapter_no",
        (f"%{name}%",)
    ).fetchall()

    # 2. 从 chapters.content 全文搜索
    content_rows = conn.execute(
        "SELECT DISTINCT chapter_no FROM chapters WHERE content LIKE ? ORDER BY chapter_no",
        (f"%{name}%",)
    ).fetchall()

    conn.close()

    focus_chs = {r[0] for r in focus_rows}
    content_chs = {r[0] for r in content_rows}
    all_chs = sorted(focus_chs | content_chs)

    if not all_chs:
        print(f"  「{name}」在所有已入库章节中均未出场")
        return

    print(f"  📖 「{name}」出场章节（共 {len(all_chs)} 章）:")
    print()
    for ch in all_chs:
        tags = []
        if ch in focus_chs:
            tags.append("聚焦")
        if ch in content_chs:
            tags.append("出现")
        print(f"    第{ch}章  {'/'.join(tags)}")


# ── 精神状态管理 ──

MENTAL_STATE_HELP = """
可用精神状况类别:
  抑郁症  PTSD  焦虑症  强迫症  PTSD（战场型）  人格障碍
  进食障碍  睡眠障碍  物质滥用  精神分裂
  双相情感障碍  恐惧症  解离性障碍  适应障碍  冲动控制障碍
"""


def _get_mental_state(name: str) -> dict:
    """从独立文件获取角色精神状态字典。"""
    return get_mental_state(PROJECT_ROOT, name)


def _char_mental_show(name: str):
    """显示角色精神状态表格."""
    ms = _get_mental_state(name)

    print(f"  ╔══ {name} 精神状态 ═══")
    print()
    has_any = False
    for cat in MENTAL_STATE_CATEGORIES:
        data = ms.get(cat, None)
        if data is None:
            continue
        has_any = True
        sev = data.get("severity", 0)
        onset = data.get("onset", "") or "—"
        triggers = ", ".join(data.get("triggers", [])) or "—"
        manifests = ", ".join(data.get("manifestations", [])) or "—"
        notes = data.get("chapter_notes", {})
        note_count = len(notes)
        bar = "█" * sev + "░" * (5 - sev)
        print(f"  {cat}")
        print(f"    严重度: {sev}/5  {bar}")
        print(f"    诱因:   {onset}")
        print(f"    触发词: {triggers}")
        print(f"    表现:   {manifests}")
        if note_count > 0:
            latest = sorted(notes.items(), key=lambda x: int(x[0]))[-3:]
            print(f"    章节追踪 ({note_count} 章):")
            for ch, note in latest:
                print(f"      第{ch}章: {note[:50]}{'…' if len(note) > 50 else ''}")
        print()

    if not has_any:
        print(f"  (该角色暂未设置任何精神状态)")
        print()
        print(f"  你可以:")
        print(f"    python novel.py character mental {name} set 抑郁症 3")
        print(f"    python novel.py character mental {name} onset PTSD 宗门被灭当晚")
        print(f"    python novel.py character mental {name} trigger 焦虑症 血月")
        print(f"    python novel.py character mental {name} manifest PTSD 噩梦惊醒")
        print(MENTAL_STATE_HELP)
    else:
        print(f"  相关命令:")
        print(f"    python novel.py character mental {name} set <类别> <0-5>")
        print(f"    python novel.py character mental {name} onset <类别> <文本>")
        print(f"    python novel.py character mental {name} trigger <类别> <词>")
        print(f"    python novel.py character mental {name} check <章节号>")
    print(f"  ╚═══")


def _char_mental_set(name: str, category: str, severity: int):
    """设置某类精神状态的 severity（0=清除）. """
    category = _normalize_mental_category(category)
    if category not in MENTAL_STATE_CATEGORIES:
        print(f"  ❌ 未知类别「{category}」")
        print(MENTAL_STATE_HELP)
        return
    if severity < 0 or severity > 5:
        print("  ❌ severity 必须在 0-5 之间")
        return

    ms = _get_mental_state(name)

    if severity == 0:
        if category in ms:
            del ms[category]
            print(f"  ✅ 已清除「{name}」的「{category}」")
        else:
            print(f"  ℹ️  「{name}」没有「{category}」记录")
            return
    else:
        if category in ms and ms[category] is not None:
            ms[category]["severity"] = severity
        else:
            ms[category] = {"severity": severity, "onset": "", "triggers": [], "manifestations": [], "chapter_notes": {}}
        print(f"  ✅ 「{name}」的「{category}」严重度 → {severity}/5")

    save_mental_state(PROJECT_ROOT, name, ms)


def _char_mental_onset(name: str, category: str, text: str):
    """设置诱因."""
    category = _normalize_mental_category(category)
    if category not in MENTAL_STATE_CATEGORIES:
        print(f"  ❌ 未知类别")
        print(MENTAL_STATE_HELP)
        return
    ms = _get_mental_state(name)
    if category not in ms or ms[category] is None:
        print(f"  ℹ️  「{category}」尚未设置，先 set severity > 0")
        return
    ms[category]["onset"] = text
    save_mental_state(PROJECT_ROOT, name, ms)
    print(f"  ✅ 「{name}」的「{category}」诱因已设置")


def _char_mental_trigger(name: str, category: str, word: str):
    """添加触发词."""
    category = _normalize_mental_category(category)
    if category not in MENTAL_STATE_CATEGORIES:
        print(f"  ❌ 未知类别")
        print(MENTAL_STATE_HELP)
        return
    ms = _get_mental_state(name)
    if category not in ms or ms[category] is None:
        print(f"  ℹ️  「{category}」尚未设置，先 set severity > 0")
        return
    triggers = ms[category].setdefault("triggers", [])
    if word not in triggers:
        triggers.append(word)
        save_mental_state(PROJECT_ROOT, name, ms)
        print(f"  ✅ 已添加触发词「{word}」")
    else:
        print(f"  ℹ️  「{word}」已在触发词列表中")


def _char_mental_manifest(name: str, category: str, description: str):
    """添加发作表现."""
    category = _normalize_mental_category(category)
    if category not in MENTAL_STATE_CATEGORIES:
        print(f"  ❌ 未知类别")
        print(MENTAL_STATE_HELP)
        return
    ms = _get_mental_state(name)
    if category not in ms or ms[category] is None:
        print(f"  ℹ️  「{category}」尚未设置，先 set severity > 0")
        return
    manifests = ms[category].setdefault("manifestations", [])
    if description not in manifests:
        manifests.append(description)
        save_mental_state(PROJECT_ROOT, name, ms)
        print(f"  ✅ 已添加表现「{description}」")
    else:
        print(f"  ℹ️  「{description}」已在表现列表中")


def _char_mental_check(name: str, chapter_no: str):
    """审核章节精神状态一致性（调用 mental_state_guard）. """
    from src.cli.commands_voice import _resolve_chapter_path
    ch_path = _resolve_chapter_path(chapter_no)
    if not ch_path:
        print(f"  ❌ 找不到第{chapter_no}章文件")
        return
    content = Path(ch_path).read_text(encoding="utf-8")
    ms = _get_mental_state(name)
    if not ms or all(v is None for v in ms.values()):
        print(f"  ℹ️  「{name}」未设置精神状态，跳过审核")
        return

    try:
        from src.guards.human_texture.mental_state_guard import run_mental_state_check
        result = run_mental_state_check(content, int(chapter_no), project_root=PROJECT_ROOT, character_name=name)
        status = result.get("status", "PASS")
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}.get(status, "❓")
        print(f"  {icon} 精神状态审核 — 第{chapter_no}章 / {name}")
        print(f"     状态: {status}")
        print()
        for issue in result.get("issues", []):
            lvl = issue.get("severity", "INFO")
            msg = issue.get("message", "")
            sug = issue.get("suggestion", "")
            iicon = {"WARN": "⚠️", "FAIL": "❌", "PASS": "✅"}.get(lvl, "💡")
            print(f"    {iicon} {msg}")
            if sug:
                print(f"         → {sug}")
    except ImportError:
        print(f"  ℹ️  mental_state_guard 未安装，执行简单关键词检查")
        _simple_mental_check(content, name, ms, chapter_no)


def _simple_mental_check(content: str, name: str, ms: dict, chapter_no: str):
    """无 guard 时的降级精神状态检查。

    Args:
        ms: mental_state dict (直接传入，不做 card 解包)
    """
    findings = []
    for cat, data in ms.items():
        if data is None:
            continue
        triggers = data.get("triggers", [])
        if not triggers:
            continue
        for t in triggers:
            if t in content:
                manifests = data.get("manifestations", [])
                has_manifest = any(m in content for m in manifests)
                if not has_manifest:
                    findings.append(f"    第{chapter_no}章出现「{cat}」触发词「{t}」，但未见对应表现")
    if findings:
        print(f"  ⚠️ 发现 {len(findings)} 个一致性问题:")
        for f in findings:
            print(f)
    else:
        print(f"  ✅ 未发现明显一致性问题")


def _char_mental_scan():
    """从大纲扫描推荐角色精神状态."""
    title, content, ch_count = _get_outline_content()
    if not title:
        print("  ⛔ 当前没有激活的大纲")
        return

    print(f"  📋 大纲: {title} ({ch_count} 章)")
    print(f"  🔍 正在扫描精神状态关键词...")
    print()

    # 加载关键词词库
    keyword_map = _load_mental_keywords()
    if not keyword_map:
        print("  ⚠️  词库加载失败，使用内置关键词")
        keyword_map = _builtin_mental_keywords()

    # 提取角色名
    extracted_names = _extract_chinese_names(content)
    db_chars = _get_db_characters()
    db_names = {c["name"] for c in db_chars}
    all_chars = sorted(extracted_names | db_names)

    if not all_chars:
        print("  ⚠️  大纲中未检测到角色名")
        return

    # v0.7.1-f: 噪声词过滤 — 单字 + 通用高频词汇
    _NOISE_WORDS = {
        "嗜", "酗", "回忆", "失败", "失去", "孤独", "压力",
        "拒绝", "穿越", "逃避", "离开", "消失", "沉默",
        "紧张", "不安", "害怕", "担心",
    }

    results = []
    for name in all_chars:
        char_results = []
        # v0.7.1-f: 角色名附近 200 字范围搜索（替代全局搜索）
        name_pos = content.find(name)
        if name_pos >= 0:
            window_start = max(0, name_pos - 200)
            window_end = min(len(content), name_pos + len(name) + 200)
            window = content[window_start:window_end]
        else:
            window = content  # 极端 fallback

        for cat, keywords in keyword_map.items():
            hit_count = 0
            hit_keywords = []
            all_kw = set()
            for kw_list in keywords.values():
                all_kw.update(kw_list)
            for kw in all_kw:
                if len(kw) <= 1 or kw in _NOISE_WORDS:
                    continue
                if kw in window:
                    hit_count += 1
                    hit_keywords.append(kw)
            if hit_count > 0:
                # v0.7.1-f: 改进 severity，降低噪音放大
                suggested = min(5, max(1, hit_count))
                char_results.append((cat, suggested, hit_keywords))

        if char_results:
            results.append((name, char_results))

    if not results:
        print("  未检测到与精神状态相关的关键词")
        return

    for name, char_results in results:
        print(f"  🎭 {name}")
        for cat, sev, hk in char_results:
            kw_str = ", ".join(hk[:5])
            extra = "…" if len(hk) > 5 else ""
            print(f"    → 建议 {cat} (severity ≥ {sev})")
            print(f"      相关关键词: {kw_str}{extra}")
        print()

    print(f"  📊 共 {len(results)} 个角色有精神状态建议")
    print()
    print(f"  设置方法:")
    for name, char_results in results[:3]:
        first_cat = char_results[0][0] if char_results else "抑郁症"
        print(f"    python novel.py character mental {name} set {first_cat} 3")


def _load_mental_keywords() -> dict:
    """从 mental_state_presets.yaml 加载关键词词库."""
    try:
        import yaml
        kf = PROJECT_ROOT / "configs" / "human_texture" / "mental_state_presets.yaml"
        if not kf.exists():
            return {}
        data = yaml.safe_load(kf.read_text(encoding="utf-8"))
        result = {}
        for cat, cfg in data.items():
            kw = cfg.get("keywords", {})
            result[cat] = kw
        return result
    except Exception:
        return {}


def _builtin_mental_keywords() -> dict:
    """内置关键词词库（降级用）. """
    return {
        "抑郁症": {"core": ["消沉", "悲观", "绝望", "虚无", "无意义", "厌倦", "孤独"]},
        "PTSD": {"core": ["创伤", "噩梦", "闪回", "惊恐", "血月", "剑鸣"]},
        "焦虑症": {"core": ["不安", "担忧", "害怕", "紧张", "焦虑", "恐慌"]},
        "强迫症": {"core": ["强迫", "反复", "必须", "对称", "计数", "洁癖"]},
        "物质滥用": {"core": ["成瘾", "依赖", "嗜", "酗", "滥用", "戒断"]},
        "精神分裂": {"core": ["幻听", "幻视", "妄想", "被害", "幻觉"]},
    }


def cmd_character(args):
    """Dispatch character subcommands."""
    action = getattr(args, "character_action", None)

    if action == "list":
        _char_list()

    elif action == "show":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py character show <角色名>")
            return
        _char_show(name)

    elif action == "create":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py character create <角色名>")
            return
        _char_create(name)

    elif action == "delete":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py character delete <角色名>")
            return
        _char_delete(name)

    elif action == "edit":
        name = getattr(args, "character_name", "")
        field = getattr(args, "field", "")
        value = getattr(args, "value", "")
        if not name or not field or value is None:
            print("  用法: python novel.py character edit <角色名> <字段> <值>")
            print()
            print("  声纹字段:", " ".join(VOICE_CARD_FIELDS))
            print("  性格字段:", " ".join(PERSONALITY_FIELDS))
            print("  做事字段:", " ".join(BEHAVIOR_FIELDS))
            print("  叙事字段:", " ".join(STORY_FIELDS))
            print()
            print("  示例: python novel.py character edit 韩烈 core 沉稳")
            print("        python novel.py character edit 韩烈 habits 咬嘴唇,搓手指")
            return
        _char_edit(name, field, value)

    elif action == "outline-check":
        create_flag = getattr(args, "create_missing", False)
        _char_outline_check(create_missing=create_flag)

    elif action == "relate":
        a = getattr(args, "char_a", "")
        b = getattr(args, "char_b", "")
        t = getattr(args, "relation_type", "")
        if a and b and t:
            _char_relate(a, b, t)
        else:
            print("  用法: python novel.py character relate <角色A> <角色B> <关系>")

    elif action == "unrelate":
        a = getattr(args, "char_a", "")
        b = getattr(args, "char_b", "")
        if a and b:
            _char_unrelate(a, b)
        else:
            print("  用法: python novel.py character unrelate <角色A> <角色B>")

    elif action == "relation-graph":
        _char_relation_graph()

    elif action == "export":
        name = getattr(args, "character_name", "")
        out = getattr(args, "output_path", "")
        if name:
            _char_export(name, out)
        else:
            print("  用法: python novel.py character export <角色名> [文件路径]")

    elif action == "import":
        fp = getattr(args, "input_path", "")
        if fp:
            _char_import(fp)
        else:
            print("  用法: python novel.py character import <文件路径>")

    elif action == "focus":
        name = getattr(args, "character_name", "")
        state = getattr(args, "focus_state", "")
        if name and state:
            _char_focus(name, state)
        else:
            print(f"  用法: python novel.py character focus <角色名> {'/'.join(FOCUS_STATE_CHOICES)}")

    elif action == "arc-check":
        _char_arc_check()

    elif action == "sync-story":
        _char_sync_story()

    elif action == "chapters":
        name = getattr(args, "character_name", "")
        if name:
            _char_chapters(name)
        else:
            print("  用法: python novel.py character chapters <角色名>")

    elif action == "check":
        ch = getattr(args, "chapter_no", "")
        inten = getattr(args, "intensity", "normal")
        if ch:
            _char_style_check(ch, inten)
        else:
            print("  用法: python novel.py character check <章节号> [--intensity light|normal|strict]")

    elif action == "mental":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py character mental <角色名> [操作]")
            print()
            print("  操作:")
            print("    (无)              — 查看角色精神状态")
            print("    show              — 查看角色精神状态")
            print("    set <类别> <0-5>   — 设置严重度（0=清除）")
            print("    onset <类别> <文本> — 设置诱因")
            print("    trigger <类别> <词> — 添加触发词")
            print("    manifest <类别> <描述> — 添加发作表现")
            print("    check <章节号>     — 审核章节精神状态一致性")
            print()
            print("  示例: python novel.py character mental 韩烈")
            print("        python novel.py character mental 韩烈 set PTSD 4")
            print("        python novel.py character mental 韩烈 onset PTSD 宗门被灭当晚")
            print("        python novel.py character mental 韩烈 trigger PTSD 血月")
            print("        python novel.py character mental 韩烈 manifest PTSD 噩梦见血月")
            print("        python novel.py character mental 韩烈 check 12")
            print(MENTAL_STATE_HELP)
            return

        sub = getattr(args, "mental_action", "show")
        arg1 = getattr(args, "mental_arg1", "")
        arg2 = getattr(args, "mental_arg2", "")

        if sub == "show" or sub is None or sub == "":
            _char_mental_show(name)
        elif sub == "set":
            if not arg1 or arg2 == "":
                print("  用法: python novel.py character mental <角色名> set <类别> <0-5>")
                return
            try:
                sev = int(arg2)
            except ValueError:
                print("  严重度必须是数字 0-5")
                return
            _char_mental_set(name, arg1, sev)
        elif sub == "onset":
            if not arg1 or not arg2:
                print("  用法: python novel.py character mental <角色名> onset <类别> <文本>")
                return
            _char_mental_onset(name, arg1, arg2)
        elif sub == "trigger":
            if not arg1 or not arg2:
                print("  用法: python novel.py character mental <角色名> trigger <类别> <词>")
                return
            _char_mental_trigger(name, arg1, arg2)
        elif sub == "manifest":
            if not arg1 or not arg2:
                print("  用法: python novel.py character mental <角色名> manifest <类别> <描述>")
                return
            _char_mental_manifest(name, arg1, arg2)
        elif sub == "check":
            if not arg1:
                print("  用法: python novel.py character mental <角色名> check <章节号>")
                return
            _char_mental_check(name, arg1)
        else:
            print(f"  ❌ 未知操作「{sub}」")
            print("  可用操作: show / set / onset / trigger / manifest / check")

    elif action == "mental-scan":
        _char_mental_scan()

    else:
        print("用法: python novel.py character {list|show|create|delete|edit|"
              "relate|unrelate|relation-graph|export|import|focus|arc-check|"
              "outline-check|mental|mental-scan}")
        print()
        print("  list                    — 列出所有角色卡")
        print("  show <角色名>            — 查看完整角色卡")
        print("  create <角色名>          — 创建默认角色卡")
        print("  delete <角色名>          — 删除角色卡")
        print("  edit <角色名> <字段> <值>  — 编辑角色字段")
        print("  relate <A> <B> <关系>    — 设置角色关系")
        print("  unrelate <A> <B>         — 删除角色关系")
        print("  relation-graph           — 文本关系图谱")
        print("  export <角色名> [文件路径] — 导出角色卡")
        print("  import <文件路径>         — 导入角色卡")
        print("  focus <角色名> <状态>     — 设置聚焦状态")
        print("  arc-check                — 弧线进度检查")
        print("  outline-check            — 从大纲检查角色卡状态")
        print("  outline-check --create   — 检查 + 自动创建缺失角色卡")
        print("  chapters <角色名>        — 查角色出场章节")
        print("  mental <角色名>           — 查看/管理精神状态（第四层）")
        print("  mental-scan              — 从大纲扫描推荐精神状态")
        print()
        print("  字段列表:")
        print("    声纹:", " ".join(VOICE_CARD_FIELDS))
        print("    性格:", " ".join(PERSONALITY_FIELDS))
        print("    做事:", " ".join(BEHAVIOR_FIELDS))
        print("    身份:", " ".join(DB_CHAR_FIELD_NAMES_EXT))
