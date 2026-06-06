#!/usr/bin/env python3
"""src/cli/commands_voice.py — 声纹卡管理 v0.6.6

命令:
  python novel.py voice list                 列出当前小说的声纹卡
  python novel.py voice show <角色名>         查看声纹卡详情
  python novel.py voice create <角色名>       创建声纹卡（交互式）
  python novel.py voice delete <角色名>       删除声纹卡
  python novel.py voice check <章节号>        检测本章角色声纹一致性
  python novel.py voice outline-check        从大纲检查所有角色声纹（可选 --create）
"""
import sys
import json
import re
from pathlib import Path
from src.cli.shared import PROJECT_ROOT, SCRIPTS_DIR, find_chapter_file
from src.guards.human_texture.voice_diversity_guard import (
    list_voice_cards, get_voice_card, save_voice_card,
    delete_voice_card, run_voice_diversity_check,
    get_active_voice_card_set, set_active_voice_card_set, list_voice_card_sets,
    VOICE_CARD_FIELDS,
)


def _resolve_chapter_path(chapter_no: str) -> str | None:
    """Find chapter file in the active slot."""
    ws_dir = PROJECT_ROOT / "workspace"
    reg_file = ws_dir / "registry.json"
    if not reg_file.exists():
        return None
    try:
        reg = json.loads(reg_file.read_text(encoding="utf-8"))
        active = reg.get("active_slot", "")
        slot_dir = ws_dir / active
        # Try chapters dir
        ch_dir = slot_dir / "chapters"
        if ch_dir.exists():
            ch_fp = find_chapter_file(int(chapter_no), ch_dir)
            if ch_fp:
                return str(ch_fp)
        # Try novels_root
        from src.cli.shared import _load_project_config, _resolve_chapter_path as _rcp
        cfg = _load_project_config()
        novels_root = Path(cfg.get("novels_root", "./novels"))
        slug = ""
        proj_file = slot_dir / "project.json"
        if proj_file.exists():
            pj = json.loads(proj_file.read_text(encoding="utf-8"))
            slug = pj.get("title") or pj.get("name", "")
        if slug:
            ch_dir = Path(_rcp(slug))
            ch_fp = find_chapter_file(int(chapter_no), ch_dir)
            if ch_fp:
                return str(ch_fp)
    except Exception:
        pass
    return None


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


def _extract_chinese_names(text: str) -> set:
    """从文本中提取中文人名。

    优先级:
    1. 从「角色:」「主角:」等字段后提取 → 最可靠
    2. 姓氏启发式（仅 2-3 字名，过滤掉明显不是人名的）"""
    surnames = set("李王张刘陈杨赵黄周吴徐孙马胡朱郭何林高罗"
                   "郑梁谢宋唐许邓韩冯曹彭曾肖田董潘袁蔡蒋余"
                   "于杜叶程苏魏吕丁任卢姚沈姜崔钟谭陆汪范金"
                   "石廖贾夏韦傅方白邹孟熊秦邱江尹薛阎段雷侯"
                   "龙史陶黎贺顾毛郝龚邵万钱严覃武戴莫孔向汤")

    reliable_names = set()
    heuristic_names = set()

    # 方法1（优先）：角色字段后提取
    for pattern in [r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[：:]\s*([^\n，。]{2,4})',
                    r'(?:主角|姓名|角色|人物|男主|女主|男配|女配)[是为叫作叫做称呼]\s*([^\n，。]{2,4})']:
        for m in re.finditer(pattern, text):
            name = m.group(1).strip()
            if 2 <= len(name) <= 4:
                reliable_names.add(name)

    # 方法2：姓氏启发式 — 仅提取 2 字名（3 字名依赖「角色:」字段和 DB）
    _punct_chars = set("，。！？、；：''（）《》…— \t,./!?;:()[]{}")
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
    }
    for i, ch in enumerate(text):
        if ch in surnames and i + 1 < len(text):
            nxt = text[i + 1]
            if nxt not in _punct_chars:
                candidate2 = text[i:i + 2]
                # 过滤词尾（不是人名的常见词）
                _bad_endings = {"场", "上", "下", "里", "前", "后", "中", "的", "了",
                                "和", "与", "在", "把", "被", "将", "对", "为",
                                "都", "也", "还", "就", "已", "能", "会", "可",
                                "来", "去", "出", "进", "到", "从", "以"}
                if candidate2[1] not in _bad_endings and candidate2 not in _COMMON_COMPOUNDS:
                    heuristic_names.add(candidate2)

    # 合并：可靠名优先
    result = set(reliable_names)
    for hn in heuristic_names:
        # 跳过可靠名的子串（避免 "韩烈" 和 "韩烈在" 等问题）
        if any(hn in rn or rn in hn for rn in reliable_names):
            continue
        # 跳过高频非人名词
        _stop = {"时候", "地方", "这里", "那里", "这边", "那边", "怎么", "什么",
                 "没有", "已经", "可以", "需要", "知道", "看见", "告诉", "开始",
                 "继续", "回到", "来到", "走出", "进入", "拿起", "放下"}
        if hn in _stop:
            continue
        if text.count(hn) < 2:
            continue
        result.add(hn)

    return {n for n in result if 2 <= len(n) <= 4}


def _cmd_voice_outline_check(create_missing: bool = False):
    """从大纲检查所有角色的声纹卡状态."""
    # 1. 获取当前活跃大纲
    mgr = __import__("scripts.outline.outline_manager", fromlist=["OutlineManager"])
    OM = getattr(mgr, "OutlineManager")
    om = OM(PROJECT_ROOT)
    outline = om.current_outline()
    if not outline:
        print("  ⛔ 当前没有激活的大纲")
        print("  先: python novel.py outline add <大纲文件>")
        return

    content = outline.get("content", "")
    title = outline.get("title", "未命名大纲")
    print(f"  📋 大纲: {title} ({outline.get('chapter_count', 0)} 章)")
    print()

    # 2. 提取角色名
    extracted_names = _extract_chinese_names(content)

    # 3. 从 DB characters 表获取注册角色
    db_chars = _get_db_characters()
    db_names = {c["name"] for c in db_chars}
    # 别名也加入
    for c in db_chars:
        alias = c.get("alias", "")
        if alias:
            for a in alias.split(","):
                a = a.strip()
                if a:
                    db_names.add(a)

    # 合并所有角色名
    all_chars = extracted_names | db_names

    if not all_chars:
        print("  ⚠️  大纲中未检测到角色名")
        print("  💡 如果角色在 characters 表中已注册，会自动识别")
        print("  💡 也可在 outline 中用「角色: 张三」格式显式标记")
        return

    # 4. 获取现有声纹卡
    cards = list_voice_cards(PROJECT_ROOT)
    card_names = {c.get("name", ""): c for c in cards}
    card_set = set(card_names.keys())

    # 5. 比对
    has_card = sorted(all_chars & card_set)
    missing = sorted(all_chars - card_set)

    print(f"  🎭 检测到 {len(all_chars)} 个角色:")
    print()

    # 按来源分类
    from_outline = extracted_names
    from_db = db_names

    for name in sorted(all_chars):
        source = []
        if name in from_outline:
            source.append("大纲")
        if name in from_db:
            source.append("DB")
        src_tag = f"[{'/'.join(source)}]"

        if name in card_set:
            card = card_names[name]
            dialect = card.get("dialect", "") or "无"
            pref = card.get("sentence_length_preference", "?")
            print(f"    ✅ {name:8s} {src_tag:12s} 方言:{dialect:6s} 句长:{pref}")
        else:
            print(f"    ❌ {name:8s} {src_tag:12s} 无声纹卡")

    print()

    if missing:
        print(f"  ⚠️  {len(missing)} 个角色尚未创建声纹卡:")
        for name in missing:
            print(f"     python novel.py voice create {name}")
        print()

        if create_missing:
            created = 0
            for name in missing:
                new_card = {
                    "sentence_length_preference": "中等",
                    "common_words": [],
                    "forbidden_words": [],
                    "emotional_leak_style": "",
                    "anger_style": "",
                    "lie_style": "",
                    "silence_style": "",
                    "humor_style": "",
                    "relationship_specific_tone": {},
                }
                ok = save_voice_card(PROJECT_ROOT, name, new_card)
                if ok:
                    created += 1
            print(f"  ✅ 已自动创建 {created}/{len(missing)} 个角色的默认声纹卡")
            # 重新计算覆盖率
            cards = list_voice_cards(PROJECT_ROOT)
            card_names = {c.get("name", ""): c for c in cards}
            card_set = set(card_names.keys())
            has_card = sorted(all_chars & card_set)
            missing = sorted(all_chars - card_set)
        else:
            print(f"  💡 加 --create 自动创建默认声纹卡")
    else:
        print("  ✅ 所有角色均已配置声纹卡")

    # 6. 检查 DB 中有但大纲中没有的角色（过时角色检测）
    extra = db_names - extracted_names
    if extra:
        print()
        print(f"  📌 DB 中有但大纲中未出现的角色（可能已过时）:")
        for name in sorted(extra):
            print(f"     {name}")

    print()
    current_set = get_active_voice_card_set(PROJECT_ROOT)
    print(f"  📁 当前声纹卡组: {current_set}")
    print(f"  📊 声纹卡覆盖率: {len(has_card)}/{len(all_chars)} ({round(len(has_card)/len(all_chars)*100) if all_chars else 0}%)")


def cmd_voice(args):
    """Dispatch voice subcommands."""
    # v0.7.1-g: deprecation warning
    print("  ⚠️ voice 命令即将在后续版本移除，请改用 character 命令")
    print("  · python novel.py character list")
    print("  · python novel.py character show <角色名>")
    print("  · python novel.py character create <角色名>")
    print()
    action = getattr(args, "voice_action", None)

    if action == "list":
        cards = list_voice_cards(PROJECT_ROOT)
        if not cards:
            print("  当前小说无声纹卡")
            print("  创建: python novel.py voice create <角色名>")
            return
        print(f"  声纹卡 ({len(cards)} 个角色):")
        for c in cards:
            name = c.get("name", c.get("_file", "?"))
            pref = c.get("sentence_length_preference", "?")
            dialect = c.get("dialect", "")
            common = c.get("common_words", [])
            print(f"    {name:8s} {dialect:6s} 句长:{pref:6s}  {' '.join(common[:3]):30s}")

    elif action == "show":
        name = getattr(args, "character_name", "")
        card = get_voice_card(PROJECT_ROOT, name)
        if not card:
            print(f"  未找到角色「{name}」的声纹卡")
            return
        print(f"  【{name}】声纹卡:")
        for field in VOICE_CARD_FIELDS:
            val = card.get(field, "")
            if val:
                if isinstance(val, list):
                    print(f"    {field}: {' '.join(val)}")
                elif isinstance(val, dict):
                    print(f"    {field}:")
                    for k, v in val.items():
                        print(f"      {k}: {v}")
                else:
                    print(f"    {field}: {val}")

    elif action == "create":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py voice create <角色名>")
            return
        card = get_voice_card(PROJECT_ROOT, name)
        if card:
            print(f"  角色「{name}」已有声纹卡，将被覆盖")
        new_card = {
            "sentence_length_preference": "中等",
            "common_words": [],
            "forbidden_words": [],
            "emotional_leak_style": "",
            "anger_style": "",
            "lie_style": "",
            "silence_style": "",
            "humor_style": "",
            "relationship_specific_tone": {},
        }
        ok = save_voice_card(PROJECT_ROOT, name, new_card)
        if ok:
            print(f"  ✅ 已创建「{name}」声纹卡")
            print(f"  编辑: D:\\DSJ\\novel-pipeline-write-engine\\workspace\\<slot>\\voice_cards\\{name}.json")
            print(f"  可用字段: {' '.join(VOICE_CARD_FIELDS)}")
        else:
            print(f"  ❌ 创建失败（无法确定当前 slot）")

    elif action == "delete":
        name = getattr(args, "character_name", "")
        if not name:
            print("  用法: python novel.py voice delete <角色名>")
            return
        ok = delete_voice_card(PROJECT_ROOT, name)
        if ok:
            print(f"  ✅ 已删除「{name}」声纹卡")
        else:
            print(f"  未找到角色「{name}」的声纹卡")

    elif action == "check":
        ch = getattr(args, "chapter_no", None)
        if not ch:
            print("  用法: python novel.py voice check <章节号>")
            return
        ch_path = _resolve_chapter_path(ch)
        if not ch_path:
            print(f"  ❌ 找不到第{ch}章文件")
            return
        content = Path(ch_path).read_text(encoding="utf-8")
        result = run_voice_diversity_check(content, int(ch), PROJECT_ROOT)
        print(f"  [voice_diversity_guard] 第{ch}章 评分: {result['score']}/100")
        for f_ in result.get("findings", []):
            lvl = f_.get("level", "INFO")
            msg = f_.get("message", "")
            sug = f_.get("suggestion", "")
            print(f"    [{lvl:5s}] {msg}")
            if sug:
                print(f"          建议: {sug}")
    elif action == "set":
        set_action = getattr(args, "voice_set_action", "")
        if set_action == "list":
            sets = list_voice_card_sets(PROJECT_ROOT)
            current = get_active_voice_card_set(PROJECT_ROOT)
            print(f"  声纹卡组 ({len(sets)} 个):")
            for s in sets:
                mark = "→ " if s == current else "  "
                print(f"    {mark}{s}")
            print(f"\n  当前: {current}")
            print("  切换: python novel.py voice set use <卡组名>")
        elif set_action == "use":
            name = getattr(args, "set_name", "")
            if not name:
                print("  用法: python novel.py voice set use <卡组名>")
                return
            ok = set_active_voice_card_set(PROJECT_ROOT, name)
            if ok:
                print(f"  ✅ 已切换到声纹卡组「{name}」")
            else:
                print("  ❌ 切换失败（无法确定当前 slot）")
        else:
            print("用法: python novel.py voice set {list|use}")
            print("  list              — 列出声纹卡组")
            print("  use <卡组名>       — 切换声纹卡组")

    elif action == "outline-check":
        create_flag = getattr(args, "create_missing", False)
        _cmd_voice_outline_check(create_missing=create_flag)

    else:
        print("用法: python novel.py voice {list|show|create|delete|check|outline-check}")
        print("  list                    — 列出声纹卡")
        print("  show <角色名>            — 查看声纹卡")
        print("  create <角色名>          — 创建声纹卡")
        print("  delete <角色名>          — 删除声纹卡")
        print("  check <章节号>           — 检测声纹一致性")
        print("  outline-check           — 从大纲检查所有角色声纹")
        print("  outline-check --create  — 检查 + 自动创建缺失声纹卡")
