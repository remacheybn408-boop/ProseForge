"""src/cli/commands_promises.py — 读者承诺管理 CLI

Commands:
  python novel.py promises list [--status open|all]
  python novel.py promises add "<描述>" [--chapter <N>] [--importance <1-5>]
  python novel.py promises fulfill <ID> <章号>
  python novel.py promises break <ID>
  python novel.py promises check [--threshold <N>]
"""

import sys
import json
import sqlite3
from datetime import datetime
from src.cli.shared import (PROJECT_ROOT, _get_active_db_path, _get_default_slug,
    _get_novel_id)


def _status_label(status):
    labels = {"open": "待兑现", "fulfilled": "已兑现", "broken": "已作废"}
    return labels.get(status, status)


def _get_max_chapter(cur, nid):
    cur.execute("SELECT MAX(chapter_no) FROM chapters WHERE novel_id=?", (nid,))
    row = cur.fetchone()
    return row[0] if row and row[0] else 0


# ── subcommand handlers ──


def _record_promise_alignment(nid, cur, promise_id, chapter_no, alignment_type, notes=""):
    """Record promise alignment in arc_alignments table."""
    cur.execute(
        "INSERT OR IGNORE INTO arc_alignments "
        "(novel_id, promise_id, chapter_no, alignment_type, notes) "
        "VALUES (?,?,?,?,?)",
        (nid, promise_id, chapter_no, alignment_type, notes),
    )
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
    if status_filter == "all":
        cur.execute(
            "SELECT id, promise_title, introduced_chapter, payoff_chapter, status, importance "
            "FROM reader_promises WHERE novel_id=? ORDER BY "
            "CASE status WHEN 'open' THEN 0 WHEN 'fulfilled' THEN 1 WHEN 'broken' THEN 2 END, "
            "importance DESC, id",
            (nid,),
        )
    else:
        cur.execute(
            "SELECT id, promise_title, introduced_chapter, payoff_chapter, status, importance "
            "FROM reader_promises WHERE novel_id=? AND status=? ORDER BY importance DESC, id",
            (nid, status_filter),
        )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        label = _status_label(status_filter) if status_filter != "all" else ""
        print(f"  当前小说无{' ' + label if label else ''}读者承诺")
        print('  添加: python novel.py promises add "<承诺描述>"')
        return
    label = _status_label(status_filter) if status_filter != "all" else "全部"
    print(f"\n  读者承诺 ({label}, {len(rows)} 条):")
    print(f"  {'ID':4s} {'承诺':28s} {'引入章':6s} {'兑现章':6s} {'状态':8s} {'重要度'}")
    print(f"  {'-'*4} {'-'*28} {'-'*6} {'-'*6} {'-'*8} {'-'*10}")
    for r in rows:
        imp_bar = "\u2605" * r["importance"] + "\u2606" * (5 - r["importance"])
        intro = str(r["introduced_chapter"] or "—")
        payoff = str(r["payoff_chapter"] or "—")
        title = r["promise_title"][:28]
        print(f"  {r['id']:<4d} {title:<28s} {intro:>6s} {payoff:>6s} {_status_label(r['status']):8s} {imp_bar}")
    print()


def _pr_add(description, chapter=None, importance=3):
    if not description:
        print('  用法: python novel.py promises add "<承诺描述>" [--chapter <N>] [--importance <1-5>]')
        return
    importance = max(1, min(5, int(importance)))
    title = description[:20] + ("..." if len(description) > 20 else "")
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
        "INSERT INTO reader_promises (novel_id, promise_title, promise_detail, introduced_chapter, status, importance) "
        "VALUES (?,?,?,?,?,?)",
        (nid, title, description, chapter, "open", importance),
    )
    conn.commit()
    rowid = cur.lastrowid
    if chapter:
        _record_promise_alignment(nid, cur, rowid, chapter, "setup",
                                  f"承诺「{title}」于第{chapter}章提出")
        conn.commit()
    conn.close()
    _sync_story_promises(title, description, chapter)
    print(f"  [OK] 已添加读者承诺 #{rowid}「{title}」")
    print(f"  列表: python novel.py promises list")
    print(f"  兑现: python novel.py promises fulfill {rowid} <章号>")


def _pr_fulfill(pid, chapter_no):
    if not pid or not chapter_no:
        print("  用法: python novel.py promises fulfill <ID> <章号>")
        return
    try:
        pid = int(pid)
        chapter_no = int(chapter_no)
    except ValueError:
        print("  [ERROR] ID 和章号必须是整数")
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
    cur.execute(
        "SELECT * FROM reader_promises WHERE id=? AND novel_id=?", (pid, nid)
    )
    row = cur.fetchone()
    if not row:
        print(f"  未找到承诺 #{pid}")
        conn.close()
        return
    if row["status"] != "open":
        print(f"  承诺 #{pid}「{row['promise_title']}」状态为 {_status_label(row['status'])}，无需再次兑现")
        conn.close()
        return
    cur.execute(
        "UPDATE reader_promises SET status='fulfilled', payoff_chapter=?, updated_at=datetime('now') WHERE id=?",
        (chapter_no, pid),
    )
    _record_promise_alignment(nid, cur, pid, chapter_no, "fulfillment",
                              f"承诺「{row['promise_title']}」于第{chapter_no}章兑现")
    conn.commit()
    conn.close()
    _update_story_promise_resolved(row["promise_title"])
    print(f"  [OK] 承诺 #{pid}「{row['promise_title']}」已在第{chapter_no}章兑现")


def _pr_break(pid):
    if not pid:
        print("  用法: python novel.py promises break <ID>")
        return
    try:
        pid = int(pid)
    except ValueError:
        print("  [ERROR] ID 必须是整数")
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
    cur.execute(
        "SELECT * FROM reader_promises WHERE id=? AND novel_id=?", (pid, nid)
    )
    row = cur.fetchone()
    if not row:
        print(f"  未找到承诺 #{pid}")
        conn.close()
        return
    if row["status"] != "open":
        print(f"  承诺 #{pid}「{row['promise_title']}」状态为 {_status_label(row['status'])}，无需再次作废")
        conn.close()
        return
    cur.execute(
        "UPDATE reader_promises SET status='broken', updated_at=datetime('now') WHERE id=?",
        (pid,),
    )
    conn.commit()
    conn.close()
    print(f"  [OK] 承诺 #{pid}「{row['promise_title']}」已作废")


def _pr_check(threshold=20):
    try:
        threshold = int(threshold)
    except ValueError:
        threshold = 20
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
    max_ch = _get_max_chapter(cur, nid)
    if max_ch == 0:
        print("  当前小说无章节数据")
        conn.close()
        return
    stale_ch = max_ch - threshold
    if stale_ch < 1:
        print(f"  当前最大章号 {max_ch}，未达到阈值 {threshold} 章，无需检查")
        conn.close()
        return
    cur.execute(
        "SELECT id, promise_title, introduced_chapter, importance "
        "FROM reader_promises WHERE novel_id=? AND status='open' AND introduced_chapter <= ? "
        "ORDER BY introduced_chapter, importance DESC",
        (nid, stale_ch),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        print(f"  [OK] 无超过 {threshold} 章未兑现的承诺")
        return
    print(f"\n  ⚠️  超过 {threshold} 章未兑现的承诺 ({len(rows)} 条):")
    print(f"  (当前进度: 第{max_ch}章)")
    print()
    print(f"  {'ID':4s} {'承诺':30s} {'引入章':6s} {'搁置章数':8s} {'重要度'}")
    print(f"  {'-'*4} {'-'*30} {'-'*6} {'-'*8} {'-'*10}")
    for r in rows:
        imp_bar = "\u2605" * r["importance"] + "\u2606" * (5 - r["importance"])
        gap = max_ch - (r["introduced_chapter"] or 0)
        intro = str(r["introduced_chapter"]) if r["introduced_chapter"] else "—"
        print(f"  {r['id']:<4d} {r['promise_title']:<30s} {intro:>6s} {gap:>8d}  {imp_bar}")
    print()
    total_penalty = len(rows) * 10
    print(f"  搁置惩罚: +{total_penalty} deviation score")
    print(f"  兑现: python novel.py promises fulfill <ID> <章号>")


def _sync_story_promises(title, detail, chapter):
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
        "detail": detail,
        "resolved": False,
        "chapter": chapter or 0,
        "added_at": datetime.now().isoformat(),
    }
    promises.append(entry)
    mem_file.write_text(json.dumps(promises, ensure_ascii=False, indent=2), encoding="utf-8")


def _update_story_promise_resolved(title):
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
        return
    updated = False
    for p in promises:
        if p.get("promise") == title and not p.get("resolved"):
            p["resolved"] = True
            updated = True
    if updated:
        mem_file.write_text(json.dumps(promises, ensure_ascii=False, indent=2), encoding="utf-8")


# ── main dispatch ──


def cmd_promises(args):
    action = getattr(args, "promises_action", None)

    if action == "list":
        _pr_list(getattr(args, "status", "open"))
    elif action == "add":
        _pr_add(
            getattr(args, "description", ""),
            chapter=getattr(args, "chapter", None),
            importance=getattr(args, "importance", 3),
        )
    elif action == "fulfill":
        _pr_fulfill(
            getattr(args, "id", None),
            getattr(args, "chapter_no", None),
        )
    elif action == "break":
        _pr_break(getattr(args, "id", None))
    elif action == "check":
        _pr_check(getattr(args, "threshold", 20))
    else:
        print("用法: python novel.py promises {list|add|fulfill|break|check}")
        print()
        print("  list [--status open|all]  — 列出承诺 (默认只显示待兑现)")
        print('  add "<描述>"               — 添加新承诺')
        print("  fulfill <ID> <章号>        — 标记某章兑现了该承诺")
        print("  break <ID>                — 标记承诺已作废")
        print("  check [--threshold <N>]   — 检查长期未兑现的承诺 (默认20章)")
        print()
        print("  add 可选参数:")
        print("    --chapter <章号>     — 在哪章提出的 (可选)")
        print("    --importance <1-5>   — 重要度 (默认3)")
        print()
        print("  示例:")
        print('    python novel.py promises add "林观澜会找到穿越的原因" --chapter 1 --importance 5')
        print("    python novel.py promises fulfill 1 10")
        print("    python novel.py promises check --threshold 15")
