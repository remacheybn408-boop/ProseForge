"""src/cli/commands_context.py — 章节上下文管理 CLI v0.7.1

context show [N]  — 查看某章上下文
context pack     — 生成全部章节压缩包
context gap      — 检测上下文断层
"""

from src.cli.shared import (PROJECT_ROOT, _load_project_config, _get_default_slug,
    _get_active_db_path)
import sys
import json
import sqlite3
from pathlib import Path


def _connect():
    db = _get_active_db_path()
    if not db or not db.exists():
        print("[ERROR] 未找到活跃数据库")
        sys.exit(1)
    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row
    conn.execute("""CREATE TABLE IF NOT EXISTS chapter_contexts (
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
    return conn


def _get_novel_id(cur):
    slug = _get_default_slug()
    cur.execute("SELECT id, title FROM novels WHERE slug=?", (slug,))
    row = cur.fetchone()
    if not row:
        print(f"[ERROR] 小说 '{slug}' 未在数据库中找到")
        sys.exit(1)
    return row["id"], row["title"], slug


def _context_show(chapter_no=None):
    """Display chapter context as a formatted table."""
    conn = _connect()
    cur = conn.cursor()
    nid, title, slug = _get_novel_id(cur)

    if chapter_no is None:
        cur.execute("SELECT MAX(chapter_no) FROM chapter_contexts WHERE novel_id=?", (nid,))
        row = cur.fetchone()
        chapter_no = row[0] if row and row[0] else 0
        if not chapter_no:
            print("暂无上下文数据。请先运行 post 生成。")
            conn.close()
            return 1
        print(f"(未指定章节号，显示最新: 第{chapter_no}章)")

    cur.execute("""
        SELECT * FROM chapter_contexts WHERE novel_id=? AND chapter_no=?
    """, (nid, chapter_no))
    ctx = cur.fetchone()
    conn.close()

    if not ctx:
        print(f"第{chapter_no}章无上下文数据。请先运行 post 生成。")
        return 1

    print(f"\n{'='*60}")
    print(f"  第{chapter_no}章 上下文 — 《{title}》")
    print(f"{'='*60}")

    # Character locations
    try:
        locs = json.loads(ctx["character_locations"]) if isinstance(ctx["character_locations"], str) else ctx["character_locations"]
    except Exception:
        locs = {}
    if locs:
        print(f"\n  📍 人物位置:")
        for name, loc in locs.items():
            print(f"    {name}: {loc}")

    # Active items
    try:
        items = json.loads(ctx["active_items"]) if isinstance(ctx["active_items"], str) else ctx["active_items"]
    except Exception:
        items = []
    if items:
        print(f"\n  🎒 活跃物品: {', '.join(items)}")

    # Unresolved threads
    try:
        threads = json.loads(ctx["unresolved_threads"]) if isinstance(ctx["unresolved_threads"], str) else ctx["unresolved_threads"]
    except Exception:
        threads = []
    if threads:
        print(f"\n  ❓ 未解决线索 ({len(threads)}):")
        for t in threads[:8]:
            print(f"    · {t}")

    # Emotional states
    try:
        emotions = json.loads(ctx["emotional_states"]) if isinstance(ctx["emotional_states"], str) else ctx["emotional_states"]
    except Exception:
        emotions = {}
    if emotions:
        print(f"\n  💭 情绪状态: {' | '.join(f'{k}={v}' for k, v in emotions.items())}")

    # World state
    if ctx["world_state"]:
        print(f"\n  🌍 环境变化: {ctx['world_state'][:200]}")

    # Ending state
    if ctx["ending_state"]:
        print(f"\n  🎬 结尾定格: {ctx['ending_state'][:200]}")

    # Hooks
    if ctx["hooks_for_next"]:
        print(f"\n  🪝 留给下章: {ctx['hooks_for_next'][:200]}")

    # Raw summary
    if ctx["raw_summary"]:
        print(f"\n  📝 摘要: {ctx['raw_summary'][:300]}")

    print()
    return 0


def _context_pack():
    """Generate full context pack for all chapters and write to file."""
    conn = _connect()
    cur = conn.cursor()
    nid, title, slug = _get_novel_id(cur)

    cur.execute("""
        SELECT chapter_no, raw_summary, character_locations, active_items, unresolved_threads
        FROM chapter_contexts WHERE novel_id=? ORDER BY chapter_no
    """, (nid,))
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("暂无上下文数据。请先运行 post 生成各章。")
        return 1

    pack_lines = [
        f"# 上下文压缩包 — 《{title}》",
        f"# 共 {len(rows)} 章",
        "",
    ]
    for row in rows:
        ch = row["chapter_no"]
        pack_lines.append(f"## 第{ch}章")
        pack_lines.append(f"  {row['raw_summary'][:200] if row['raw_summary'] else '(无摘要)'}")
        try:
            locs = json.loads(row["character_locations"]) if isinstance(row["character_locations"], str) else (row["character_locations"] or {})
            if locs:
                pack_lines.append(f"  位置: {' | '.join(f'{k}={v}' for k, v in locs.items())}")
        except Exception:
            pass
        try:
            items = json.loads(row["active_items"]) if isinstance(row["active_items"], str) else (row["active_items"] or [])
            if items:
                pack_lines.append(f"  物品: {', '.join(items)}")
        except Exception:
            pass
        pack_lines.append("")

    export_dir = Path("exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    pack_path = export_dir / "context_pack.txt"
    pack_path.write_text("\n".join(pack_lines), encoding="utf-8")
    print(f"\n✅ 上下文压缩包已生成: {pack_path}")
    print(f"   共 {len(rows)} 章, {pack_path.stat().st_size} bytes")
    return 0


def _context_gap():
    """Detect context gaps between consecutive chapters."""
    conn = _connect()
    cur = conn.cursor()
    nid, title, slug = _get_novel_id(cur)

    # Get all character names
    cur.execute("SELECT name FROM characters WHERE novel_id=?", (nid,))
    char_names = set(r[0] for r in cur.fetchall())

    cur.execute("""
        SELECT chapter_no, character_locations, active_items, unresolved_threads
        FROM chapter_contexts WHERE novel_id=? ORDER BY chapter_no
    """, (nid,))
    rows = cur.fetchall()

    if len(rows) < 2:
        conn.close()
        print("需要至少 2 章上下文才能检测断层。")
        return 1

    # 承诺断裂检测
    max_ch = max(r["chapter_no"] for r in rows)
    stale_threshold = max_ch - 20
    stale_promises = []
    if stale_threshold >= 1:
        cur.execute(
            "SELECT promise_title, introduced_chapter FROM reader_promises "
            "WHERE novel_id=? AND status='open' AND introduced_chapter <= ? "
            "ORDER BY introduced_chapter",
            (nid, stale_threshold),
        )
        stale_promises = cur.fetchall()
    conn.close()

    print(f"\n{'='*60}")
    print(f"  上下文断层检测 — 《{title}》")
    print(f"{'='*60}\n")

    gaps_found = 0
    for i in range(len(rows) - 1):
        prev = rows[i]
        curr = rows[i + 1]
        prev_ch = prev["chapter_no"]
        curr_ch = curr["chapter_no"]

        # Parse locations
        try:
            prev_locs = json.loads(prev["character_locations"]) if isinstance(prev["character_locations"], str) else (prev["character_locations"] or {})
            curr_locs = json.loads(curr["character_locations"]) if isinstance(curr["character_locations"], str) else (curr["character_locations"] or {})
        except Exception:
            prev_locs = {}
            curr_locs = {}

        # Parse items
        try:
            prev_items = set(json.loads(prev["active_items"]) if isinstance(prev["active_items"], str) else (prev["active_items"] or []))
            curr_items = set(json.loads(curr["active_items"]) if isinstance(curr["active_items"], str) else (curr["active_items"] or []))
        except Exception:
            prev_items = set()
            curr_items = set()

        # Detect gaps
        issues = []

        # Location jump: character moves without explanation
        for name in char_names:
            if name in prev_locs and name in curr_locs:
                if prev_locs[name] != curr_locs[name]:
                    issues.append(f"    {name}: {prev_locs[name]} → {curr_locs[name]} (位置跳变)")

        # Item disappearance: item was active in prev but gone in curr without resolution
        dropped_items = prev_items - curr_items
        if dropped_items:
            issues.append(f"    物品消失: {', '.join(sorted(dropped_items)[:5])}")

        if issues:
            gaps_found += 1
            print(f"  ⚠️ 第{prev_ch}章 → 第{curr_ch}章:")
            for issue in issues:
                print(issue)
            print()

    # ── 承诺断裂检测 ──
    if stale_promises:
        print(f"\n  📝 承诺断裂检测 (超过 20 章未兑现的承诺, {len(stale_promises)} 条):")
        for sp in stale_promises:
            gap = max_ch - (sp["introduced_chapter"] or 0)
            print(f"    ⚠ 「{sp['promise_title']}」第{sp['introduced_chapter']}章提出，已搁置 {gap} 章")
        gaps_found += len(stale_promises)

    if gaps_found == 0:
        print("  ✅ 未检测到上下文断层")

    print(f"\n  共检测 {len(rows)-1} 个过渡，发现 {gaps_found} 个断层")
    return 0


def cmd_context(args):
    """Dispatch context sub-commands."""
    action = getattr(args, "context_action", None)

    if action == "show" or action is None:
        chapter_no = getattr(args, "chapter_no", None)
        if chapter_no:
            try:
                chapter_no = int(chapter_no)
            except ValueError:
                print(f"[ERROR] 无效章节号: {chapter_no}")
                return 1
        return _context_show(chapter_no)

    elif action == "pack":
        return _context_pack()

    elif action == "gap":
        return _context_gap()

    else:
        print(f"未知 context 子命令: {action}")
        print("可用: show [N], pack, gap")
        return 1
