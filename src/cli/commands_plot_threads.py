"""src/cli/commands_plot_threads.py — 情节线管理 CLI

Commands:
  python novel.py plot-threads list
  python novel.py plot-threads show <title>
  python novel.py plot-threads create <title> [--type <类型>] [--content <描述>] [--importance <1-5>] [--chapter <章号>]
  python novel.py plot-threads edit <title> <field> <value>
  python novel.py plot-threads close <title> [--chapter <章号>]
  python novel.py plot-threads advance <chapter_no> <title>
  python novel.py plot-threads timeline
"""

import sys
import json
import sqlite3
from datetime import datetime
from src.cli.shared import (PROJECT_ROOT, _get_active_db_path, _get_default_slug,
    _get_novel_id, _find_by_title)


def _status_label(status):
    labels = {"open": "进行中", "active": "活跃", "resolved": "已完结", "abandoned": "已放弃"}
    return labels.get(status, status)


def _thread_type_label(t):
    labels = {"伏笔": "伏笔", "主线": "主线", "支线": "支线", "感情线": "感情线", "成长线": "成长线"}
    return labels.get(t, t)


# ── subcommand handlers ──


def _record_thread_alignment(nid, cur, thread_id, chapter_no, alignment_type, notes=""):
    """Record plot thread alignment in arc_alignments table."""
    cur.execute(
        "INSERT OR IGNORE INTO arc_alignments "
        "(novel_id, thread_id, chapter_no, alignment_type, notes) "
        "VALUES (?,?,?,?,?)",
        (nid, thread_id, chapter_no, alignment_type, notes),
    )


def _pt_list():
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
        "SELECT title, thread_type, status, importance, introduced_chapter, resolved_chapter "
        "FROM plot_threads WHERE novel_id=? ORDER BY "
        "CASE status WHEN 'open' THEN 0 WHEN 'active' THEN 1 WHEN 'resolved' THEN 2 WHEN 'abandoned' THEN 3 END, "
        "importance DESC, title",
        (nid,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print("  当前小说无情节线索")
        print('  创建: python novel.py plot-threads create "<线索名>"')
        return
    print(f"\n  情节线索 ({len(rows)} 条):")
    print(f"  {'线索':20s} {'类型':10s} {'状态':8s} {'重要度':10s} {'起始章':6s} {'完结章'}")
    print(f"  {'-'*20} {'-'*10} {'-'*8} {'-'*10} {'-'*6} {'-'*8}")
    for r in rows:
        imp_bar = "\u2605" * r["importance"] + "\u2606" * (5 - r["importance"])
        intro = str(r["introduced_chapter"] or "—")
        resolved = str(r["resolved_chapter"] or "—")
        print(f"  {r['title']:20s} {_thread_type_label(r['thread_type']):10s} "
              f"{_status_label(r['status']):8s} {imp_bar:10s} {intro:>6s} {resolved:>8s}")
    print()


def _pt_show(title):
    if not title:
        print("  用法: python novel.py plot-threads show <线索名>")
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
    row = _find_by_title(cur, "plot_threads", nid, title)
    if not row:
        print(f'  未找到情节线索「{title}」')
        conn.close()
        return

    # Find chapters that planned to advance this thread
    cur.execute(
        "SELECT chapter_no, plot_threads_to_advance FROM chapter_plans "
        "WHERE plot_threads_to_advance LIKE ? ORDER BY chapter_no",
        (f"%{row['title']}%",),
    )
    plan_refs = cur.fetchall()
    conn.close()

    imp_bar = "\u2605" * row["importance"] + "\u2606" * (5 - row["importance"])
    print(f'\n  ╔══ 情节线索 —— {row["title"]}')
    print(f'  ┌─ 类型: {_thread_type_label(row["thread_type"])}')
    print(f'  ├─ 状态: {_status_label(row["status"])}')
    print(f'  ├─ 重要度: {imp_bar} ({row["importance"]}/5)')
    print(f'  ├─ 起始章: 第{row["introduced_chapter"]}章' if row["introduced_chapter"] else '  ├─ 起始章: (未设置)')
    print(f'  ├─ 完结章: 第{row["resolved_chapter"]}章' if row["resolved_chapter"] else '  ├─ 完结章: (未完结)')
    print(f"  └─ 内容:")
    content = row["content"] or "(暂无描述)"
    for line in content.split("\n"):
        print(f"     {line}")
    if plan_refs:
        print(f"\n  📋 计划推进此线索的章节 ({len(plan_refs)} 章):")
        for pr in plan_refs:
            print(f"     第{pr['chapter_no']}章: {pr['plot_threads_to_advance'][:80]}")
    print(f"  ╚═══")
    print()


def _pt_create(title, thread_type="伏笔", content="", importance=3, introduced_chapter=None):
    if not title:
        print('  用法: python novel.py plot-threads create <线索名> [--type <类型>] [--content <描述>] [--importance <1-5>] [--chapter <起始章>]')
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
    cur.execute("SELECT id FROM plot_threads WHERE novel_id=? AND title=?", (nid, title))
    if cur.fetchone():
        print(f'  情节线索「{title}」已存在，使用 edit 更新')
        conn.close()
        return
    cur.execute(
        "INSERT INTO plot_threads (novel_id, title, content, thread_type, status, importance, introduced_chapter) "
        "VALUES (?,?,?,?,?,?,?)",
        (nid, title, content, thread_type, "open", importance, introduced_chapter),
    )
    conn.commit()
    rowid = cur.lastrowid
    try:
        cur.execute(
            "INSERT INTO novel_plot_fts (rowid, title, content) VALUES (?,?,?)",
            (rowid, title, content),
        )
        conn.commit()
    except Exception:
        pass
    conn.close()
    _sync_story_promises(title, content, thread_type)
    print(f'  [OK] 已创建情节线索「{title}」')
    print(f'  查看: python novel.py plot-threads show "{title}"')
    if not content:
        print(f'  编辑描述: python novel.py plot-threads edit "{title}" content "详细描述"')


def _pt_edit(title, field, value):
    ALLOWED_FIELDS = {"thread_type", "content", "importance", "introduced_chapter", "resolved_chapter"}
    if not title or not field or value is None:
        print("  用法: python novel.py plot-threads edit <线索名> <字段> <值>")
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
    if field in ("introduced_chapter", "resolved_chapter"):
        try:
            value = int(value)
        except ValueError:
            print(f"  [ERROR] {field} 必须是整数章号")
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
    row = _find_by_title(cur, "plot_threads", nid, title)
    if not row:
        print(f'  未找到情节线索「{title}」')
        conn.close()
        return
    cur.execute(f"UPDATE plot_threads SET {field}=? WHERE id=?", (value, row["id"]))
    conn.commit()
    if field in ("title", "content"):
        try:
            cur.execute("DELETE FROM novel_plot_fts WHERE rowid=?", (row["id"],))
            cur.execute(
                "INSERT INTO novel_plot_fts (rowid, title, content) "
                "SELECT id, title, content FROM plot_threads WHERE id=?",
                (row["id"],),
            )
            conn.commit()
        except Exception:
            pass
    conn.close()
    print(f'  [OK] 已更新「{row["title"]}」的 {field} = {value}')


def _pt_close(title, chapter=None):
    if not title:
        print("  用法: python novel.py plot-threads close <线索名> [--chapter <章号>]")
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
    row = _find_by_title(cur, "plot_threads", nid, title)
    if not row:
        print(f'  未找到情节线索「{title}」')
        conn.close()
        return
    if row["status"] == "resolved":
        print(f'  线索「{row["title"]}」已完结 (第{row["resolved_chapter"]}章)')
        conn.close()
        return
    if chapter:
        cur.execute(
            "UPDATE plot_threads SET status='resolved', resolved_chapter=? WHERE id=?",
            (int(chapter), row["id"]),
        )
    else:
        cur.execute(
            "UPDATE plot_threads SET status='resolved' WHERE id=?",
            (row["id"],),
        )
    _record_thread_alignment(nid, cur, row["id"], chapter or 0, "resolution",
                             f"线索「{row['title']}」已完结" + (f" (第{chapter}章)" if chapter else ""))
    conn.commit()
    conn.close()
    msg = f'  [OK] 已完结线索「{row["title"]}」'
    if chapter:
        msg += f" (第{chapter}章)"
    print(msg)


def _pt_advance(chapter_no, title):
    if not chapter_no or not title:
        print("  用法: python novel.py plot-threads advance <章号> <线索名>")
        return
    try:
        chapter_no = int(chapter_no)
    except ValueError:
        print(f"  [ERROR] 无效章号: {chapter_no}")
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
    row = _find_by_title(cur, "plot_threads", nid, title)
    if not row:
        print(f'  未找到情节线索「{title}」')
        conn.close()
        return
    if row["status"] == "resolved":
        print(f'  线索「{row["title"]}」已完结，无法继续推进。使用 reopen 或 create 创建新线索。')
        conn.close()
        return
    # Set introduced_chapter if not set; mark as active
    updates = ["status='active'"]
    params = []
    if not row["introduced_chapter"]:
        updates.append("introduced_chapter=?")
        params.append(chapter_no)
    params.append(row["id"])
    cur.execute(
        f"UPDATE plot_threads SET {', '.join(updates)} WHERE id=?",
        (*params,),
    )
    _record_thread_alignment(nid, cur, row["id"], chapter_no, "progress",
                             f"线索「{row['title']}」在第{chapter_no}章推进")
    conn.commit()
    conn.close()
    print(f'  [OK] 第{chapter_no}章推进了线索「{row["title"]}」')


def _pt_timeline():
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
        "SELECT title, thread_type, status, importance, introduced_chapter, resolved_chapter "
        "FROM plot_threads WHERE novel_id=? ORDER BY "
        "COALESCE(introduced_chapter, 999), importance DESC",
        (nid,),
    )
    threads = cur.fetchall()
    if not threads:
        print("  当前小说无情节线索")
        conn.close()
        return
    # Build chapter plan references
    cur.execute(
        "SELECT chapter_no, plot_threads_to_advance FROM chapter_plans "
        "WHERE plot_threads_to_advance IS NOT NULL AND plot_threads_to_advance != '' "
        "ORDER BY chapter_no",
    )
    plan_refs = cur.fetchall()
    conn.close()

    # Build chapter -> threads map from plans
    ch_plan_map = {}
    for pr in plan_refs:
        ch = pr["chapter_no"]
        text = pr["plot_threads_to_advance"]
        ch_plan_map.setdefault(ch, []).append(text[:120])

    print(f"\n  ╔══ 情节线索时间线 ({len(threads)} 条)")
    # Find chapter range
    all_chs = set()
    for t in threads:
        if t["introduced_chapter"]:
            all_chs.add(t["introduced_chapter"])
        if t["resolved_chapter"]:
            all_chs.add(t["resolved_chapter"])
    for ch in ch_plan_map:
        all_chs.add(ch)
    min_ch = min(all_chs) if all_chs else 1
    max_ch = max(all_chs) if all_chs else 1

    print(f"  章节范围: 第{min_ch}章 — 第{max_ch}章\n")
    for t in threads:
        intro = t["introduced_chapter"]
        resolved = t["resolved_chapter"]
        status = _status_label(t["status"])
        imp_bar = "\u2605" * t["importance"] + "\u2606" * (5 - t["importance"])
        # Build visual bar: ░ for inactive chapters, █ for active span
        span_start = intro or min_ch
        span_end = resolved if t["status"] == "resolved" else max_ch
        bar = ""
        for ch in range(min_ch, max_ch + 1):
            if ch == intro:
                bar += "\u2503"  # start
            elif ch == resolved and t["status"] == "resolved":
                bar += "\u2716"  # resolved
            elif span_start <= ch <= span_end:
                bar += "\u2503"  # active
            else:
                bar += "\u00b7"  # inactive
        print(f"  [{imp_bar}] {t['title']:<18s} [{_thread_type_label(t['thread_type']):6s}] {status:6s}")
        print(f"  {bar}")
        if intro:
            print(f"  起始: 第{intro}章", end="")
            if t["status"] == "resolved" and resolved:
                print(f" → 完结: 第{resolved}章", end="")
            print()
        print()

    # Chapter plan summary
    if ch_plan_map:
        print(f"  ── 章节计划中涉及的线索推进 ──")
        for ch in sorted(ch_plan_map):
            notes = ch_plan_map[ch]
            print(f"  第{ch}章: {notes[0]}")
            if len(notes) > 1:
                for n in notes[1:]:
                    print(f"         {n}")
        print()

    print(f"  ╚═══")
    print()


def _sync_story_promises(title, content, thread_type):
    """Sync to .story/memory/promises.json for story contract system."""
    from src.cli.shared import _get_story_dir
    story_dir = _get_story_dir()
    if not story_dir:
        return
    mem_file = story_dir / "memory" / "promises.json"
    if not mem_file.exists():
        return
    try:
        promises = json.loads(mem_file.read_text(encoding="utf-8"))
    except Exception:
        promises = []
    entry = {
        "promise": title,
        "type": thread_type,
        "description": content[:200] if content else "",
        "resolved": False,
        "chapter": 0,
        "added_at": datetime.now().isoformat(),
    }
    promises.append(entry)
    mem_file.write_text(json.dumps(promises, ensure_ascii=False, indent=2), encoding="utf-8")


# ── main dispatch ──


def cmd_plot_threads(args):
    action = getattr(args, "plot_threads_action", None)

    if action == "list":
        _pt_list()
    elif action == "show":
        _pt_show(getattr(args, "title", ""))
    elif action == "create":
        _pt_create(
            getattr(args, "title", ""),
            thread_type=getattr(args, "thread_type", "伏笔"),
            content=getattr(args, "content", ""),
            importance=getattr(args, "importance", 3),
            introduced_chapter=getattr(args, "chapter", None),
        )
    elif action == "edit":
        _pt_edit(
            getattr(args, "title", ""),
            getattr(args, "field", ""),
            getattr(args, "value", ""),
        )
    elif action == "close":
        _pt_close(
            getattr(args, "title", ""),
            chapter=getattr(args, "chapter", None),
        )
    elif action == "advance":
        _pt_advance(
            getattr(args, "chapter_no", None),
            getattr(args, "title", ""),
        )
    elif action == "timeline":
        _pt_timeline()
    else:
        print("用法: python novel.py plot-threads {list|show|create|edit|close|advance|timeline}")
        print()
        print("  list              — 列出所有情节线索")
        print("  show <线索名>      — 查看完整线索")
        print('  create "<线索名>"   — 创建新线索')
        print("  edit <线索名> <字段> <值> — 编辑线索字段")
        print("  close <线索名>     — 标记已完结")
        print("  advance <章号> <线索名> — 标记某章推进了该线索")
        print("  timeline          — 线索时间线")
        print()
        print("  create 可选参数:")
        print("    --type <类型>       — 伏笔/主线/支线/感情线/成长线 (默认伏笔)")
        print("    --content <描述>    — 详细描述")
        print("    --importance <1-5>  — 重要度 (默认3)")
        print("    --chapter <章号>     — 起始章号")
        print()
        print("  edit 可用字段: thread_type content importance introduced_chapter resolved_chapter")
