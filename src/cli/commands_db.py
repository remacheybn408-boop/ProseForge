#!/usr/bin/env python3
"""src/cli/commands_db.py — CLI commands for novel-pipeline-write-engine v0.6.5"""

from src.cli.shared import PROJECT_ROOT, SCRIPTS_DIR, _get_workspace_dir, _get_active_db_path
import sys
import json
from pathlib import Path
from datetime import datetime
from version import get_version
from scripts.config_utils import normalize_config, load_json_config, resolve_path

def cmd_db(args):
    """Multi-DB workspace management commands."""
    action = getattr(args, "db_action", None)

    if action == "init":
        return _db_init(getattr(args, "force", False))
    elif action == "list":
        return _db_list()
    elif action == "current":
        return _db_current()
    elif action == "info":
        return _db_info()
    elif action == "new":
        return _db_new(getattr(args, "name", ""), getattr(args, "description", ""))
    elif action == "use":
        return _db_use(getattr(args, "slot_id", ""))
    elif action == "delete":
        return _db_delete(
            getattr(args, "slot_id", ""),
            yes=getattr(args, "yes", False),
        )
    elif action == "trash":
        return _db_trash()
    elif action == "restore":
        return _db_restore(
            getattr(args, "slot_id", ""),
            backup_id=getattr(args, "backup_id", None),
            from_trash=getattr(args, "from_trash", False),
        )
    elif action == "purge":
        return _db_purge(getattr(args, "trash_name", None))
    elif action == "backup":
        return _db_backup(getattr(args, "slot", None))
    else:
        print("用法: python novel.py db {init|list|current|info|new|use|delete|trash|restore|purge|backup}")
        print()
        print("  init         初始化 workspace 目录结构")
        print("  list         列出所有 DB slot")
        print("  current      显示当前活跃 DB slot")
        print("  info         显示当前 slot 详细信息")
        print("  new          创建新 DB slot (--name <名称>)")
        print("  use          切换到指定 DB slot")
        print("  delete       安全删除 DB slot (移至回收站, --yes 确认)")
        print("  trash        查看回收站中的 slot")
        print("  restore      从备份恢复 DB slot (--from-trash 从回收站恢复)")
        print("  purge        永久删除回收站中的 slot")
        print("  backup       备份当前 DB slot")
        return 1


def _db_init(force=False):
    """Initialize workspace directory structure."""
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if registry_file.exists() and not force:
        print("  workspace/ 已经初始化。")
        print("  使用 --force 强制重新初始化。")
        return 0

    import json as _json
    from datetime import datetime

    # Create workspace directory
    ws_dir.mkdir(parents=True, exist_ok=True)

    # Create initial registry
    registry = {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "active_slot": "slot_001",
        "slots": [
            {
                "id": "slot_001",
                "name": "默认工作区",
                "description": "默认项目工作区",
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "project_count": 0,
            }
        ],
    }
    registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  [OK] workspace/registry.json 已创建")

    # Create 3 initial slots
    for i in range(1, 4):
        slot_id = f"slot_{i:03d}"
        slot_dir = ws_dir / slot_id
        _create_slot_structure(slot_dir)
        print(f"  [OK] {slot_id}/ 目录已创建")

    # P0-5: Register all 3 slots in registry (not just slot_001)
    if len(registry["slots"]) < 3:
        registry["slots"].append({
            "id": "slot_002", "name": "空闲工作区 2",
            "description": "空闲工作区", "status": "normal",
            "created_at": datetime.now().isoformat(), "project_count": 0,
        })
        registry["slots"].append({
            "id": "slot_003", "name": "空闲工作区 3",
            "description": "空闲工作区", "status": "normal",
            "created_at": datetime.now().isoformat(), "project_count": 0,
        })
        registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    # P0-1 clean3: Migrate all existing slot DBs to include FTS5 tables
    for i in range(1, 4):
        slot_id = f"slot_{i:03d}"
        slot_dir = ws_dir / slot_id
        if slot_dir.exists():
            _migrate_slot_fts(slot_dir)

    print()
    print("  workspace 初始化完成！")
    print(f"  活跃 slot: slot_001")
    print(f"  使用 python novel.py db new --name <名称> 创建更多工作区")
    return 0


def _create_slot_structure(slot_dir: Path):
    """Create standard slot directory structure including novel.db."""
    import json as _json
    import sqlite3
    from datetime import datetime

    slot_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ["outlines", "chapters", "reports", "exports", "backups"]:
        (slot_dir / subdir).mkdir(parents=True, exist_ok=True)

    # P0-2: Create per-slot novel.db with full schema (if not exists)
    db_path = slot_dir / "novel.db"
    if not db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS novels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    genre TEXT DEFAULT '',
                    theme TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    target_words INTEGER DEFAULT 0,
                    current_words INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'planning',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT DEFAULT 'note',
                    project TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    importance INTEGER DEFAULT 3,
                    source TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    last_used_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS volumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    title TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    target_words INTEGER DEFAULT 0,
                    UNIQUE(novel_id, volume_no)
                );

                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_id INTEGER REFERENCES volumes(id),
                    chapter_no INTEGER NOT NULL,
                    title TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    word_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    file_path TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, chapter_no)
                );

                CREATE TABLE IF NOT EXISTS chapter_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    chunk_no INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    name TEXT NOT NULL,
                    alias TEXT DEFAULT '',
                    role TEXT DEFAULT '',
                    identity TEXT DEFAULT '',
                    personality TEXT DEFAULT '',
                    motivation TEXT DEFAULT '',
                    ability TEXT DEFAULT '',
                    relationship TEXT DEFAULT '',
                    arc TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    focus_state TEXT DEFAULT '活跃',
                    tags TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS worldbuilding (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    category TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    importance INTEGER DEFAULT 3,
                    tags TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS plot_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    thread_type TEXT DEFAULT '伏笔',
                    introduced_chapter INTEGER,
                    resolved_chapter INTEGER,
                    status TEXT DEFAULT 'open',
                    importance INTEGER DEFAULT 3
                );

                CREATE TABLE IF NOT EXISTS writing_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    rule_type TEXT DEFAULT 'other',
                    importance INTEGER DEFAULT 3,
                    status TEXT DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS chapter_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    short_summary TEXT DEFAULT '',
                    long_summary TEXT DEFAULT '',
                    key_events TEXT DEFAULT '',
                    characters_involved TEXT DEFAULT '',
                    new_settings TEXT DEFAULT '',
                    foreshadowing TEXT DEFAULT '',
                    continuity_notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, chapter_id)
                );

                CREATE TABLE IF NOT EXISTS continuity_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    check_type TEXT DEFAULT 'continuity',
                    issue TEXT DEFAULT '',
                    suggestion TEXT DEFAULT '',
                    severity INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'open',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS novel_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id INTEGER,
                    detail TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS chapter_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER,
                    chapter_no INTEGER NOT NULL,
                    version_no INTEGER NOT NULL DEFAULT 1,
                    version_status TEXT DEFAULT 'draft',
                    title TEXT DEFAULT '',
                    content TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    change_reason TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS reader_promises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    promise_title TEXT NOT NULL,
                    promise_detail TEXT NOT NULL,
                    introduced_chapter INTEGER,
                    expected_payoff_range TEXT DEFAULT '',
                    payoff_chapter INTEGER,
                    status TEXT DEFAULT 'open',
                    importance INTEGER DEFAULT 3,
                    reader_emotion TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS volume_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    planned_title TEXT DEFAULT '',
                    final_title TEXT DEFAULT '',
                    title_status TEXT DEFAULT 'planned',
                    suggested_chapters INTEGER DEFAULT 25,
                    min_chapters INTEGER DEFAULT 20,
                    max_chapters INTEGER DEFAULT 29,
                    volume_goal TEXT DEFAULT '',
                    opening_state TEXT DEFAULT '',
                    ending_target TEXT DEFAULT '',
                    must_complete TEXT DEFAULT '',
                    unresolved_hooks_to_next TEXT DEFAULT '',
                    outline_version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, volume_no)
                );

                CREATE TABLE IF NOT EXISTS chapter_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    chapter_no INTEGER NOT NULL,
                    planned_title TEXT DEFAULT '',
                    final_title TEXT DEFAULT '',
                    title_status TEXT DEFAULT 'planned',
                    plan_status TEXT DEFAULT 'planned',
                    chapter_goal TEXT DEFAULT '',
                    main_event TEXT DEFAULT '',
                    character_focus TEXT DEFAULT '',
                    conflict_point TEXT DEFAULT '',
                    must_include TEXT DEFAULT '',
                    plot_threads_to_advance TEXT DEFAULT '',
                    reader_promises_to_advance TEXT DEFAULT '',
                    ending_hook_direction TEXT DEFAULT '',
                    continuity_from_previous TEXT DEFAULT '',
                    title_change_reason TEXT DEFAULT '',
                    actual_word_count INTEGER DEFAULT 0,
                    actual_summary TEXT DEFAULT '',
                    completion_status TEXT DEFAULT '',
                    ingested_at TEXT DEFAULT '',
                    outline_version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, volume_no, chapter_no)
                );

                CREATE TABLE IF NOT EXISTS title_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER,
                    chapter_no INTEGER,
                    old_title TEXT DEFAULT '',
                    new_title TEXT DEFAULT '',
                    title_type TEXT DEFAULT 'chapter',
                    change_reason TEXT DEFAULT '',
                    changed_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS chapter_contexts (
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
                );

                -- FTS5 全文检索索引 (v0.6.5-clean3)
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
                    title, content, summary,
                    content='chapters', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
                    content, summary,
                    content='chapter_chunks', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_character_fts USING fts5(
                    name, alias, identity, personality, tags,
                    content='characters', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_world_fts USING fts5(
                    title, content, tags,
                    content='worldbuilding', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_plot_fts USING fts5(
                    title, content,
                    content='plot_threads', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    title, content, tags,
                    content='memories', content_rowid='id'
                );
            """)
            conn.commit()
        finally:
            conn.close()

    # Create project.json if not exists
    proj_file = slot_dir / "project.json"
    if not proj_file.exists():
        proj_file.write_text(_json.dumps({
            "name": slot_dir.name,
            "title": "未命名项目",
            "active_outline": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")


def _migrate_slot_fts(slot_dir: Path) -> bool:
    """Ensure a slot's novel.db has FTS5 tables (idempotent migration)."""
    import sqlite3
    db_path = slot_dir / "novel.db"
    if not db_path.exists():
        return False
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
                title, content, summary,
                content='chapters', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
                content, summary,
                content='chapter_chunks', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_character_fts USING fts5(
                name, alias, identity, personality, tags,
                content='characters', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_world_fts USING fts5(
                title, content, tags,
                content='worldbuilding', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_plot_fts USING fts5(
                title, content,
                content='plot_threads', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                title, content, tags,
                content='memories', content_rowid='id'
            );
        """)
        conn.commit()
        return True
    finally:
        conn.close()


def _db_list():
    """List all DB slots with detailed info."""
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = registry.get("active_slot", "")
    slots = registry.get("slots", [])

    print("=" * 70)
    print("  作品列表")
    print("=" * 70)
    print()

    if not slots:
        print("  暂无作品。用「创建一本新小说的工作区」来添加第一本吧！")
        return 0

    for s in slots:
        sid = s.get("id", "?")
        name = s.get("name", "")
        status = s.get("status", "?")
        desc = s.get("description", "")
        is_active = (sid == active)

        # ── 读取 slot 目录下的详细信息 ──
        slot_dir = ws_dir / sid
        outline_title = ""
        outline_count = 0
        chapter_count = 0
        db_real_count = 0
        word_count = 0

        if slot_dir.exists():
            # 统计大纲
            outlines_dir = slot_dir / "outlines"
            if outlines_dir.exists():
                outline_files = list(outlines_dir.glob("*.json"))
                outline_count = len(outline_files)

            # 读取 project.json 获取活跃大纲标题
            proj_file = slot_dir / "project.json"
            if proj_file.exists():
                try:
                    proj = _json.loads(proj_file.read_text(encoding="utf-8"))
                    active_oid = proj.get("active_outline", "")
                    if active_oid:
                        o_file = outlines_dir / f"{active_oid}.json" if outlines_dir.exists() else None
                        if o_file and o_file.exists():
                            o_data = _json.loads(o_file.read_text(encoding="utf-8"))
                            outline_title = o_data.get("title", "")
                            chapter_count = o_data.get("chapter_count", 0)
                except Exception:
                    pass

            # P1-5: 从 novel.db 统计章节和字数（真实数据）
            db_file = slot_dir / "novel.db"
            if db_file.exists():
                try:
                    import sqlite3
                    conn = sqlite3.connect(str(db_file))
                    cur = conn.execute("SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM chapters")
                    row = cur.fetchone()
                    if row:
                        db_ch_count, db_wc = row
                        chapter_count = max(chapter_count, db_ch_count or 0)
                        word_count = db_wc or 0
                        db_real_count = db_ch_count or 0
                    else:
                        db_real_count = 0
                    conn.close()
                except Exception:
                    pass

        # ── 显示 ──
        marker = "★" if is_active else " "
        status_cn = "当前使用中" if is_active else ("正常" if status == "active" else status)

        print(f"  {marker} [{sid}] {name}")
        print(f"      状态: {status_cn}")
        if outline_title:
            print(f"      大纲: {outline_title}")
        print(f"      大纲版本数: {outline_count}  |  已写: {db_real_count} 章 / 规划 {chapter_count} 章  |  总字数: {word_count:,}")
        if desc:
            print(f"      描述: {desc}")
        print()

    print(f"  共 {len(slots)} 个作品，当前正在写: {active}")
    return 0


def _db_current():
    """Show current active DB slot."""
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = registry.get("active_slot", "")

    if not active:
        print("  当前无活跃 slot。运行 python novel.py db use <slot_id>")
        return 0

    # Find slot info
    slot_info = None
    for s in registry.get("slots", []):
        if s.get("id") == active:
            slot_info = s
            break

    print(f"  当前活跃 DB slot: {active}")
    if slot_info:
        print(f"  名称: {slot_info.get('name', '')}")
        desc = slot_info.get("description", "")
        if desc:
            print(f"  描述: {desc}")
        print(f"  项目数: {slot_info.get('project_count', 0)}")
    return 0


def _db_info():
    """Show detailed info about current slot."""
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = registry.get("active_slot", "")
    slot_dir = ws_dir / active

    print("=" * 60)
    print(f"  DB Slot 详细信息: {active}")
    print("=" * 60)
    print()

    # Registry info
    slot_info = None
    for s in registry.get("slots", []):
        if s.get("id") == active:
            slot_info = s
            break

    if slot_info:
        print(f"  名称: {slot_info.get('name', '')}")
        print(f"  描述: {slot_info.get('description', '(无)')}")
        print(f"  状态: {slot_info.get('status', '?')}")
        print(f"  创建时间: {slot_info.get('created_at', '?')}")
        print(f"  项目数: {slot_info.get('project_count', 0)}")
    print()

    # Directory structure
    print(f"  目录: {slot_dir}")
    if slot_dir.exists():
        print("  子目录:")
        for subdir in ["outlines", "chapters", "reports", "exports", "backups"]:
            exists = (slot_dir / subdir).exists()
            mark = "✓" if exists else "✗"
            count = len(list((slot_dir / subdir).iterdir())) if exists else 0
            print(f"    {mark} {subdir}/ ({count} 项)")
    else:
        print("  ⚠️  目录不存在！")

    # project.json
    proj_file = slot_dir / "project.json"
    if proj_file.exists():
        proj = _json.loads(proj_file.read_text(encoding="utf-8"))
        print()
        print("  项目信息:")
        print(f"    名称: {proj.get('title', proj.get('name', '?'))}")
        print(f"    活跃大纲: {proj.get('active_outline', '(未设定)')}")
        print(f"    最后更新: {proj.get('updated_at', '?')}")
    print()
    return 0


def _db_new(name, description=""):
    """Create a new DB slot."""
    import json as _json
    from datetime import datetime
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    slots = registry.get("slots", [])

    # Collect existing slot IDs
    existing_ids = set()
    max_idx = 0
    for s in slots:
        sid = s.get("id", "")
        if sid.startswith("slot_"):
            existing_ids.add(sid)
            try:
                idx = int(sid.replace("slot_", ""))
                if idx > max_idx:
                    max_idx = idx
            except ValueError:
                pass

    # ── 先扫描空 slot 复用 ──
    slot_id = None
    for i in range(1, max_idx + 2):
        candidate = f"slot_{i:03d}"
        if candidate not in existing_ids:
            continue
        candidate_dir = ws_dir / candidate
        if not candidate_dir.exists():
            continue
        db_file = candidate_dir / "novel.db"
        if not db_file.exists():
            slot_id = candidate
            break
        # DB exists — check if chapters table is empty
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_file))
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) as cnt FROM chapters")
            row = cur.fetchone()
            conn.close()
            if row and row["cnt"] == 0:
                slot_id = candidate
                break
        except Exception:
            # DB exists but can't be read — treat as empty for reuse
            slot_id = candidate
            break

    reused = slot_id is not None
    if not slot_id:
        next_idx = max_idx + 1
        slot_id = f"slot_{next_idx:03d}"

        if max_idx >= 3 and (max_idx + 1) % 4 == 0:
            print(f"  ℹ️  已满 {max_idx} 个 slot，正在创建 {slot_id}（将自动扩展后续 slot）。")

    # Create slot structure
    slot_dir = ws_dir / slot_id
    _create_slot_structure(slot_dir)

    # Update project.json with name
    proj_file = slot_dir / "project.json"
    proj = _json.loads(proj_file.read_text(encoding="utf-8"))
    proj["name"] = name
    proj["title"] = name
    proj["updated_at"] = datetime.now().isoformat()
    proj_file.write_text(_json.dumps(proj, ensure_ascii=False, indent=2), encoding="utf-8")

    # Add to registry (or update existing entry if reusing)
    if reused:
        for s in slots:
            if s.get("id") == slot_id:
                s["name"] = name
                s["description"] = description
                s["status"] = "active"
                s["updated_at"] = datetime.now().isoformat()
                break
    else:
        new_slot = {
            "id": slot_id,
            "name": name,
            "description": description,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "project_count": 1,
        }
        slots.append(new_slot)
    registry["slots"] = slots
    registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    if reused:
        print(f"  ✅ 复用空 slot {slot_id}，已重置！")
    else:
        print(f"  ✅ 新 DB slot {slot_id} 创建成功！")
    print(f"  Slot ID: {slot_id}")
    print(f"  名称: {name}")
    if description:
        print(f"  描述: {description}")
    print(f"  目录: {slot_dir}")
    print()
    print(f"  使用 python novel.py db use {slot_id} 切换到此工作区")
    return 0


def _db_use(slot_id):
    """Switch to a different DB slot."""
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    # 数字简写: "1" → "slot_001"
    if slot_id.isdigit():
        slot_id = f"slot_{int(slot_id):03d}"

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))

    # Verify slot exists
    slot_dir = ws_dir / slot_id
    if not slot_dir.exists():
        print(f"  ❌ Slot {slot_id} 不存在。")
        slots = [s.get("id") for s in registry.get("slots", [])]
        if slots:
            print(f"  可用 slot: {', '.join(slots)}")
        return 1

    # Verify in registry
    found = False
    for s in registry.get("slots", []):
        if s.get("id") == slot_id:
            found = True
            break
    if not found:
        print(f"  ⚠️  {slot_id} 目录存在但未在注册表中。正在添加...")
        from datetime import datetime
        registry["slots"].append({
            "id": slot_id,
            "name": slot_id,
            "description": "",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "project_count": 0,
        })

    old_active = registry.get("active_slot", "")
    registry["active_slot"] = slot_id
    registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✅ 已切换到 {slot_id}")
    if old_active and old_active != slot_id:
        print(f"  (之前: {old_active})")

    # Show slot info
    proj_file = slot_dir / "project.json"
    if proj_file.exists():
        proj = _json.loads(proj_file.read_text(encoding="utf-8"))
        print(f"  项目: {proj.get('title', proj.get('name', '?'))}")
        outline = proj.get("active_outline", "")
        if outline:
            print(f"  大纲: {outline}")
    return 0


def _db_delete(slot_id, yes=False):
    """Safe delete a DB slot — moves to workspace/_trash/ by default.

    With --yes flag, performs safe delete (move to trash).
    Without --yes, prompts for confirmation.
    """
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = registry.get("active_slot", "")

    if slot_id == active:
        print(f"  ❌ 不能删除当前活跃的 slot ({slot_id})。")
        print(f"  请先切换到其他 slot: python novel.py db use <other>")
        return 1

    if slot_id == "slot_001":
        print(f"  ⚠️  slot_001 是默认工作区，不能删除。")
        return 1

    # Verify slot exists
    if not any(s.get("id") == slot_id for s in registry.get("slots", [])):
        print(f"  ❌ Slot {slot_id} 不在注册表中。")
        return 1

    # Require confirmation
    if not yes:
        print(f"  ⚠️  即将安全删除 slot {slot_id}（移至回收站）。")
        print(f"  使用 --yes 确认删除。")
        print(f"  查看回收站: python novel.py db trash")
        return 1

    # Use SlotManager for safe trash-based deletion
    try:
        from scripts.db.slot_manager import SlotManager
        mgr = SlotManager(PROJECT_ROOT)
        result = mgr.delete_slot_safe(slot_id, confirm=True)

        if result["status"] == "ok":
            print(f"  ✅ {result['message']}")
            print(f"  回收站标识: {result.get('trash_name', '?')}")
            remaining = len(registry.get("slots", [])) - 1
            print(f"  剩余 slot: {remaining} 个")
            print()
            print(f"  提示: 使用 python novel.py db trash 查看回收站")
            print(f"       使用 python novel.py db restore --from-trash {result.get('trash_name', '')} 恢复")
            print(f"       使用 python novel.py db purge {result.get('trash_name', '')} 永久删除")
            return 0
        else:
            print(f"  ❌ 删除失败: {result.get('message', '未知错误')}")
            return 1
    except ImportError:
        # Fallback: old-style permanent delete with confirmation
        print(f"  ⚠️  SlotManager 不可用，回退到永久删除模式。")
        print(f"  确认永久删除 {slot_id} 吗？此操作不可逆！")
        print(f"  使用 --yes 确认。")
        return 1


def _db_restore(slot_id, backup_id=None, from_trash=False):
    """Restore a DB slot from backup or from trash.

    With --from-trash: restore from workspace/_trash/ (trash_name format).
    Without --from-trash: restore from slot's backup directory (existing behavior).
    """
    if from_trash:
        return _db_restore_from_trash(slot_id)

    import json as _json
    from datetime import datetime
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    slot_dir = ws_dir / slot_id
    backup_dir = slot_dir / "backups"

    if not backup_dir.exists():
        print(f"  ❌ {slot_id} 没有备份目录。")
        return 1

    # Find backups
    backups = sorted(backup_dir.glob("*.json"), reverse=True)
    if not backups:
        print(f"  ❌ {slot_id} 没有可用的备份文件。")
        return 1

    target = None
    if backup_id:
        for b in backups:
            if backup_id in b.name:
                target = b
                break
        if not target:
            print(f"  ❌ 未找到备份 {backup_id}")
            print(f"  可用备份: {', '.join(b.name for b in backups)}")
            return 1
    else:
        target = backups[0]  # Latest

    print(f"  从备份恢复: {target.name}")
    print(f"  备份时间: {datetime.fromtimestamp(target.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}")

    # Restore project.json from backup
    try:
        backup_data = _json.loads(target.read_text(encoding="utf-8"))
        proj_file = slot_dir / "project.json"
        proj_file.write_text(_json.dumps(backup_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ project.json 已从备份恢复。")

        # Also update registry
        registry = _json.loads(registry_file.read_text(encoding="utf-8"))
        for s in registry.get("slots", []):
            if s.get("id") == slot_id:
                s["status"] = "active"
                s["name"] = backup_data.get("name", backup_data.get("title", s.get("name", slot_id)))
                break
        registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ 注册表已更新。")
    except Exception as e:
        print(f"  ❌ 恢复失败: {e}")
        return 1

    return 0


def _db_backup(slot=None):
    """Backup the current DB slot's project.json."""
    import json as _json
    from datetime import datetime
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = slot or registry.get("active_slot", "")

    if not active:
        print("  ❌ 无活跃 slot。请指定 --slot <id> 或先切换。")
        return 1

    slot_dir = ws_dir / active
    proj_file = slot_dir / "project.json"
    backup_dir = slot_dir / "backups"

    if not proj_file.exists():
        print(f"  ⚠️  {active}/project.json 不存在，创建模板...")
        _create_slot_structure(slot_dir)

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Read current project.json
    proj = _json.loads(proj_file.read_text(encoding="utf-8"))
    proj["backed_up_at"] = datetime.now().isoformat()

    # Create backup file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"backup_{timestamp}.json"
    backup_file.write_text(_json.dumps(proj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✅ 备份完成！")
    print(f"  Slot: {active}")
    print(f"  备份文件: backup_{timestamp}.json")
    print(f"  位置: {backup_file}")
    return 0


# === P1-3: Trash management CLI helpers ===

def _db_trash():
    """List items in workspace/_trash/."""
    ws_dir = _get_workspace_dir()
    trash_dir = ws_dir / "_trash"

    if not trash_dir.exists():
        print("  回收站为空。")
        return 0

    try:
        from scripts.db.slot_manager import SlotManager
        mgr = SlotManager(PROJECT_ROOT)
        items = mgr.list_trash()
    except ImportError:
        items = []
        for entry in sorted(trash_dir.iterdir(), key=lambda p: p.name, reverse=True):
            if entry.is_dir():
                size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                items.append({
                    "trash_name": entry.name,
                    "original_slot_id": entry.name.split("_", 2)[-1] if "_" in entry.name else entry.name,
                    "trashed_at": "",
                    "size_bytes": size,
                })

    if not items:
        print("  回收站为空。")
        return 0

    print("=" * 60)
    print("  回收站 (workspace/_trash/)")
    print("=" * 60)
    print()

    for item in items:
        trash_name = item.get("trash_name", "?")
        original = item.get("original_slot_id", "?")
        trashed_at = item.get("trashed_at", "")
        size = item.get("size_bytes", 0)

        if trashed_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(trashed_at)
                trashed_at = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass

        size_str = f"{size:,}B" if size < 1024 else f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/(1024*1024):.1f}MB"
        print(f"  🗑️  {trash_name}")
        print(f"     原始 Slot: {original}")
        if trashed_at:
            print(f"     删除时间: {trashed_at}")
        print(f"     大小: {size_str}")
        print()

    print(f"  共 {len(items)} 项")
    print()
    print(f"  恢复: python novel.py db restore --from-trash <trash_name>")
    print(f"  永久删除: python novel.py db purge <trash_name>")
    print(f"  清空回收站: python novel.py db purge")
    return 0


def _db_restore_from_trash(trash_name):
    """Restore a slot from workspace/_trash/."""
    if not trash_name:
        print("  ❌ 请指定回收站中的项目名。")
        print("  使用 python novel.py db trash 查看回收站。")
        return 1

    try:
        from scripts.db.slot_manager import SlotManager
        mgr = SlotManager(PROJECT_ROOT)
        result = mgr.restore_slot_from_trash(trash_name)

        if result["status"] == "ok":
            print(f"  ✅ {result['message']}")
            print(f"  Slot ID: {result.get('slot_id', '?')}")
            print()
            print(f"  切换到恢复的 slot: python novel.py db use {result.get('slot_id', '')}")
            return 0
        else:
            print(f"  ❌ 恢复失败: {result.get('message', '未知错误')}")
            available = result.get("available", [])
            if available:
                print(f"  回收站中可用的项目: {', '.join(available)}")
            return 1
    except ImportError:
        # Fallback: manual restore
        ws_dir = _get_workspace_dir()
        trash_dir = ws_dir / "_trash"
        source = trash_dir / trash_name

        if not source.exists():
            print(f"  ❌ 回收站中未找到: {trash_name}")
            return 1

        # Try to determine original slot ID
        parts = trash_name.split("_", 2)
        slot_id = parts[2] if len(parts) >= 3 else trash_name
        target = ws_dir / slot_id

        if target.exists():
            print(f"  ❌ Slot {slot_id} 已存在于 workspace 中。")
            return 1

        import shutil
        shutil.move(str(source), str(target))
        print(f"  ✅ 已恢复 {slot_id} (手动模式)")
        print(f"  请运行 python novel.py db init --force 重建注册表。")
        return 0


def _db_purge(trash_name=None):
    """Permanently delete items from workspace/_trash/."""
    try:
        from scripts.db.slot_manager import SlotManager
        mgr = SlotManager(PROJECT_ROOT)
        result = mgr.purge_trash(trash_name)

        if result["status"] == "ok":
            if trash_name:
                print(f"  ✅ {result['message']}")
            else:
                purged = result.get("purged", [])
                if not purged:
                    print("  回收站为空，无需清空。")
                else:
                    print(f"  ✅ 已永久删除 {len(purged)} 项:")
                    for name in purged:
                        print(f"     - {name}")
            return 0
        elif result["status"] == "partial":
            print(f"  ⚠️  {result['message']}")
            for err in result.get("errors", []):
                print(f"     ❌ {err['item']}: {err['error']}")
            return 1
        else:
            print(f"  ❌ {result.get('message', '未知错误')}")
            return 1
    except ImportError:
        # Fallback: manual purge
        import shutil
        ws_dir = _get_workspace_dir()
        trash_dir = ws_dir / "_trash"

        if not trash_dir.exists():
            print("  回收站为空。")
            return 0

        if trash_name:
            target = trash_dir / trash_name
            if target.exists():
                shutil.rmtree(str(target))
                print(f"  ✅ 已永久删除: {trash_name}")
            else:
                print(f"  ❌ 未找到: {trash_name}")
                return 1
        else:
            count = 0
            for entry in list(trash_dir.iterdir()):
                if entry.is_dir():
                    shutil.rmtree(str(entry))
                    count += 1
            print(f"  ✅ 已永久删除 {count} 项")
        return 0

