"""src/cli/commands_worldbuilding.py — 世界观管理 CLI

Commands:
  python novel.py worldbuilding list
  python novel.py worldbuilding show <title>
  python novel.py worldbuilding add "<title>" [--category <cat>] [--content <text>] [--importance <1-5>] [--tags <tags>]
  python novel.py worldbuilding edit <title> <field> <value>
  python novel.py worldbuilding delete <title>
  python novel.py worldbuilding outline-scan
"""

import sys
import json
import sqlite3
from datetime import datetime
from src.cli.shared import (PROJECT_ROOT, _get_active_db_path, _get_default_slug,
    _get_outline_manager, _get_novel_id, _find_by_title)


def _get_outline_content():
    mgr = _get_outline_manager()
    outline = mgr.current_outline()
    if not outline:
        return ("", "")
    return (outline.get("content", ""), outline.get("title", "未命名大纲"))


def _sync_world_facts(title, content, category, tags):
    from src.cli.shared import _get_story_dir
    story_dir = _get_story_dir()
    if not story_dir:
        return
    mem_file = story_dir / "memory" / "world_facts.json"
    if not mem_file.exists():
        return
    try:
        facts = json.loads(mem_file.read_text(encoding="utf-8"))
    except Exception:
        facts = []
    entry = {
        "title": title,
        "category": category,
        "tags": tags,
        "content_summary": content[:200] if content else "",
        "added_at": datetime.now().isoformat(),
    }
    facts.append(entry)
    mem_file.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")


def _guess_category(keyword):
    if any(keyword.endswith(s) for s in ["世界", "大陆", "星球", "宇宙", "位面", "次元", "时空", "领域", "秘境"]):
        return "地理"
    if any(keyword.endswith(s) for s in ["境界", "功法", "修炼", "体系", "法则", "规则"]):
        return "修炼体系"
    if any(keyword.endswith(s) for s in ["宗派", "门派", "学院", "联盟", "帝国", "王国", "城市", "国度", "圣地"]):
        return "组织势力"
    if keyword in ["修仙", "魔法", "武道", "科技", "异能", "玄幻", "奇幻", "科幻", "末世", "穿越", "重生"]:
        return "世界类型"
    if keyword in ["灵气", "斗气", "魔力", "法力", "神念", "神识", "元婴", "金丹", "筑基", "炼气", "剑修", "体修"]:
        return "能量/境界"
    return "其他"


# ── subcommand handlers ──


def _wb_list():
    db = _get_active_db_path()
    if not db or not db.exists():
        print("[ERROR] 未找到活跃数据库")
        return
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    nid = _get_novel_id(cur)
    if nid is None:
        print("  当前小说未在数据库注册")
        conn.close()
        return
    cur.execute(
        "SELECT title, category, importance, tags FROM worldbuilding "
        "WHERE novel_id=? ORDER BY COALESCE(category,''), importance DESC, title",
        (nid,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print("  当前小说无世界观条目")
        print('  添加: python novel.py worldbuilding add "<标题>"')
        return
    print(f"\n  世界观条目 ({len(rows)} 个):")
    print(f"  {'标题':20s} {'分类':12s} {'重要度':12s} {'标签'}")
    print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*30}")
    for r in rows:
        imp_bar = "\u2605" * r["importance"] + "\u2606" * (5 - r["importance"])
        print(f"  {r['title']:20s} {r['category'] or '—':12s} {imp_bar:10s}  {r['tags'] or '—'}")
    print()


def _wb_show(title):
    if not title:
        print("  用法: python novel.py worldbuilding show <标题>")
        return
    db = _get_active_db_path()
    if not db or not db.exists():
        print("[ERROR] 未找到活跃数据库")
        return
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    nid = _get_novel_id(cur)
    if nid is None:
        print("  当前小说未在数据库注册")
        conn.close()
        return
    row = _find_by_title(cur, "worldbuilding", nid, title)
    conn.close()
    if not row:
        print(f'  未找到世界观条目「{title}」')
        print("  提示: 使用 worldbuilding list 查看所有条目")
        return
    imp_bar = "\u2605" * row["importance"] + "\u2606" * (5 - row["importance"])
    print(f'\n  ╔══ 世界观 —— {row["title"]}')
    print(f'  ┌─ 分类: {row["category"] or "未分类"}')
    print(f'  ├─ 重要度: {imp_bar} ({row["importance"]}/5)')
    print(f'  ├─ 标签: {row["tags"] or "无"}')
    print(f"  └─ 内容:")
    content = row["content"] or "(暂无内容)"
    for line in content.split("\n"):
        print(f"     {line}")
    print(f"  ╚═══")
    print()


def _wb_add(title, category="", content="", importance=3, tags=""):
    if not title:
        print('  用法: python novel.py worldbuilding add "<标题>" [--category <分类>] [--content <内容>] [--importance <1-5>] [--tags <标签>]')
        return
    importance = max(1, min(5, int(importance)))
    db = _get_active_db_path()
    if not db or not db.exists():
        print("[ERROR] 未找到活跃数据库")
        return
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    nid = _get_novel_id(cur)
    if nid is None:
        print("  当前小说未在数据库注册")
        conn.close()
        return
    cur.execute("SELECT id FROM worldbuilding WHERE novel_id=? AND title=?", (nid, title))
    if cur.fetchone():
        print(f'  世界观条目「{title}」已存在，使用 edit 更新')
        conn.close()
        return
    cur.execute(
        "INSERT INTO worldbuilding (novel_id, category, title, content, importance, tags) VALUES (?,?,?,?,?,?)",
        (nid, category, title, content, importance, tags),
    )
    conn.commit()
    rowid = cur.lastrowid
    try:
        cur.execute(
            "INSERT INTO novel_world_fts (rowid, title, content, tags) VALUES (?,?,?,?)",
            (rowid, title, content, tags),
        )
        conn.commit()
    except Exception:
        pass
    conn.close()
    _sync_world_facts(title, content, category, tags)
    print(f'  [OK] 已添加世界观条目「{title}」')
    print(f'  查看: python novel.py worldbuilding show "{title}"')
    if not content:
        print(f'  编辑内容: python novel.py worldbuilding edit "{title}" content "详细描述"')


def _wb_edit(title, field, value):
    ALLOWED_FIELDS = {"category", "content", "importance", "tags"}
    if not title or not field or value is None:
        print("  用法: python novel.py worldbuilding edit <标题> <字段> <值>")
        print(f"  可用字段: {' '.join(sorted(ALLOWED_FIELDS))}")
        return
    if field not in ALLOWED_FIELDS:
        print(f'  [ERROR] 未知字段「{field}」，可用: {" ".join(sorted(ALLOWED_FIELDS))}')
        return
    if field == "importance":
        try:
            value = str(max(1, min(5, int(value))))
        except ValueError:
            print("  [ERROR] importance 必须是 1-5 的整数")
            return
    db = _get_active_db_path()
    if not db or not db.exists():
        print("[ERROR] 未找到活跃数据库")
        return
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    nid = _get_novel_id(cur)
    if nid is None:
        print("  当前小说未在数据库注册")
        conn.close()
        return
    row = _find_by_title(cur, "worldbuilding", nid, title)
    if not row:
        print(f'  未找到世界观条目「{title}」')
        conn.close()
        return
    cur.execute(f"UPDATE worldbuilding SET {field}=? WHERE id=?", (value, row["id"]))
    conn.commit()
    if field in ("title", "content", "tags"):
        try:
            cur.execute("DELETE FROM novel_world_fts WHERE rowid=?", (row["id"],))
            cur.execute(
                "INSERT INTO novel_world_fts (rowid, title, content, tags) "
                "SELECT id, title, content, tags FROM worldbuilding WHERE id=?",
                (row["id"],),
            )
            conn.commit()
        except Exception:
            pass
    conn.close()
    print(f'  [OK] 已更新「{row["title"]}」的 {field} = {value}')


def _wb_delete(title):
    if not title:
        print("  用法: python novel.py worldbuilding delete <标题>")
        return
    db = _get_active_db_path()
    if not db or not db.exists():
        print("[ERROR] 未找到活跃数据库")
        return
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    nid = _get_novel_id(cur)
    if nid is None:
        print("  当前小说未在数据库注册")
        conn.close()
        return
    row = _find_by_title(cur, "worldbuilding", nid, title)
    if not row:
        print(f'  未找到世界观条目「{title}」')
        conn.close()
        return
    try:
        cur.execute("DELETE FROM novel_world_fts WHERE rowid=?", (row["id"],))
        conn.commit()
    except Exception:
        pass
    cur.execute("DELETE FROM worldbuilding WHERE id=?", (row["id"],))
    conn.commit()
    conn.close()
    print(f'  [OK] 已删除世界观条目「{row["title"]}」')


def _wb_outline_scan():
    content, outline_title = _get_outline_content()
    if not content:
        print("  ⛔ 当前没有激活的大纲")
        return
    from scripts.outline.similarity import _extract_world_keywords
    keywords = _extract_world_keywords(content)
    if not keywords:
        print("  大纲中未检测到世界观关键词")
        return

    db = _get_active_db_path()
    conn = sqlite3.connect(str(db)) if db and db.exists() else None
    existing_titles = set()
    if conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        nid = _get_novel_id(cur)
        if nid:
            cur.execute(
                "SELECT title FROM worldbuilding WHERE novel_id=?",
                (nid,),
            )
            existing_titles = {r["title"] for r in cur.fetchall()}
        conn.close()

    print(f"\n  📋 大纲: {outline_title}")
    print(f"  🔍 检测到 {len(keywords)} 个世界观关键词:\n")

    categorized = {}
    for kw in sorted(keywords):
        cat = _guess_category(kw)
        categorized.setdefault(cat, []).append(kw)

    for cat, kws in sorted(categorized.items()):
        print(f"  [{cat}]")
        for kw in sorted(kws):
            status = "[OK]" if kw in existing_titles else "[?] 未收录"
            print(f"    {status} {kw}")

    missing = [kw for kw in keywords if kw not in existing_titles]
    print()
    if missing:
        print(f"  ⚠️  {len(missing)} 个关键词尚未收录为世界观条目:")
        for kw in sorted(missing)[:10]:
            print(f'     python novel.py worldbuilding add "{kw}"')
        if len(missing) > 10:
            print(f"     ...及其他 {len(missing) - 10} 个")
    else:
        print("  [OK] 所有关键词均已收录")


# ── main dispatch ──


def cmd_worldbuilding(args):
    action = getattr(args, "worldbuilding_action", None)

    if action == "list":
        _wb_list()
    elif action == "show":
        _wb_show(getattr(args, "title", ""))
    elif action == "add":
        _wb_add(
            getattr(args, "title", ""),
            category=getattr(args, "category", ""),
            content=getattr(args, "content", ""),
            importance=getattr(args, "importance", 3),
            tags=getattr(args, "tags", ""),
        )
    elif action == "edit":
        _wb_edit(
            getattr(args, "title", ""),
            getattr(args, "field", ""),
            getattr(args, "value", ""),
        )
    elif action == "delete":
        _wb_delete(getattr(args, "title", ""))
    elif action == "outline-scan":
        _wb_outline_scan()
    else:
        print("用法: python novel.py worldbuilding {list|show|add|edit|delete|outline-scan}")
        print()
        print("  list            — 列出所有世界观条目")
        print("  show <标题>      — 查看完整条目")
        print('  add "<标题>"      — 添加新条目')
        print("  edit <标题> <字段> <值> — 编辑条目字段")
        print("  delete <标题>    — 删除条目")
        print("  outline-scan    — 从大纲扫描世界观关键词")
        print()
        print("  add 可选参数:")
        print("    --category <分类>   — 如 地理/修炼体系/组织势力/世界类型")
        print("    --content <内容>    — 详细描述")
        print("    --importance <1-5>  — 重要度 (默认3)")
        print("    --tags <标签1,标签2> — 逗号分隔标签")
