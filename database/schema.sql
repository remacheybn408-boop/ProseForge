-- ============================================================
-- Novel Pipeline - Write Engine
-- SQLite Schema (V1)
-- ============================================================

-- ============================================================
-- 一、通用记忆底座
-- ============================================================

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
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

CREATE TABLE IF NOT EXISTS memory_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    target_type TEXT,
    target_id INTEGER,
    detail TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now'))
);

-- ============================================================
-- 二、小说业务层
-- ============================================================

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
    tags TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS worldbuilding (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    novel_id INTEGER NOT NULL REFERENCES novels(id),
    category TEXT DEFAULT '',
    title TEXT NOT NULL,
    content TEXT DEFAULT '',
    importance INTEGER DEFAULT 3,
    tags TEXT DEFAULT ''
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

-- ============================================================
-- 三、版本与承诺
-- ============================================================

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

-- ============================================================
-- 四、卷级与章节规划（标题骨架）
-- ============================================================

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

-- ============================================================
-- 五、FTS5 全文检索索引
-- ============================================================

CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
    title, content, tags,
    content='memories', content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
    title, content, summary,
    content='chapters', content_rowid='id'
);

CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
    content, summary, tags,
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
