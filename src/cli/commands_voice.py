#!/usr/bin/env python3
"""src/cli/commands_voice.py — 声纹卡管理 v0.6.6

命令:
  python novel.py voice list             列出当前小说的声纹卡
  python novel.py voice show <角色名>     查看声纹卡详情
  python novel.py voice create <角色名>   创建声纹卡（交互式）
  python novel.py voice delete <角色名>   删除声纹卡
  python novel.py voice check <章节号>    检测本章角色声纹一致性
"""
import sys
import json
from pathlib import Path
from src.cli.shared import PROJECT_ROOT, SCRIPTS_DIR
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
            candidates = sorted(ch_dir.glob(f"第{chapter_no}章*.txt"))
            if candidates:
                return str(candidates[0])
        # Try novels_root
        from src.cli.shared import _load_project_config
        cfg = _load_project_config()
        novels_root = Path(cfg.get("novels_root", "./novels"))
        slug = ""
        proj_file = slot_dir / "project.json"
        if proj_file.exists():
            pj = json.loads(proj_file.read_text(encoding="utf-8"))
            slug = pj.get("title") or pj.get("name", "")
        if slug:
            ch_dir = novels_root / slug / "第01卷"
            candidates = sorted(ch_dir.glob(f"第{chapter_no}章*.txt"))
            if candidates:
                return str(candidates[0])
    except Exception:
        pass
    return None


def cmd_voice(args):
    """Dispatch voice subcommands."""
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

    else:
        print("用法: python novel.py voice {list|show|create|delete|check}")
        print("  list                    — 列出声纹卡")
        print("  show <角色名>            — 查看声纹卡")
        print("  create <角色名>          — 创建声纹卡")
        print("  delete <角色名>          — 删除声纹卡")
        print("  check <章节号>           — 检测声纹一致性")
