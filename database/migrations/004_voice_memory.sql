-- ============================================================
-- v0.4.5 Voice Memory Extension
-- Multi-Register Voice System + Long-Term Voice Memory
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  filename TEXT UNIQUE NOT NULL,
  applied_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS voice_packs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  pack_id TEXT UNIQUE NOT NULL,
  pack_type TEXT NOT NULL DEFAULT 'dialect',
  name TEXT DEFAULT '',
  description TEXT DEFAULT '',
  markers_json TEXT DEFAULT '[]',
  soft_markers_json TEXT DEFAULT '[]',
  danger_markers_json TEXT DEFAULT '[]',
  allowed_contexts_json TEXT DEFAULT '[]',
  forbidden_contexts_json TEXT DEFAULT '[]',
  sample_lines_json TEXT DEFAULT '[]',
  max_density_per_1000_chars INTEGER DEFAULT 6,
  overuse_warning_threshold INTEGER DEFAULT 5,
  status TEXT DEFAULT 'active',
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS character_voice_profiles (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  novel_id INTEGER NOT NULL REFERENCES novels(id),
  character_id INTEGER REFERENCES characters(id),
  character_name TEXT NOT NULL,
  voice_type TEXT DEFAULT '',
  dialect_pack TEXT DEFAULT 'none',
  register_pack TEXT DEFAULT 'none',
  meme_pack TEXT DEFAULT 'none',
  english_pack TEXT DEFAULT 'none',
  dialect_level INTEGER DEFAULT 0,
  meme_level INTEGER DEFAULT 0,
  english_level INTEGER DEFAULT 0,
  wenyan_level INTEGER DEFAULT 0,
  favorite_words_json TEXT DEFAULT '[]',
  forbidden_words_json TEXT DEFAULT '[]',
  allowed_english_json TEXT DEFAULT '[]',
  banned_english_json TEXT DEFAULT '[]',
  sample_lines_json TEXT DEFAULT '[]',
  notes TEXT DEFAULT '',
  phase TEXT DEFAULT 'default',
  status TEXT DEFAULT 'active',
  source TEXT DEFAULT 'manual',
  created_at TEXT DEFAULT (datetime('now')),
  updated_at TEXT DEFAULT (datetime('now')),
  UNIQUE(novel_id, character_name, phase)
);

CREATE TABLE IF NOT EXISTS character_voice_examples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  novel_id INTEGER NOT NULL REFERENCES novels(id),
  character_name TEXT NOT NULL,
  example_type TEXT DEFAULT 'sample',
  text TEXT NOT NULL,
  source_chapter_no INTEGER,
  source TEXT DEFAULT '',
  quality TEXT DEFAULT 'good',
  notes TEXT DEFAULT '',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS character_voice_observations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  novel_id INTEGER NOT NULL REFERENCES novels(id),
  chapter_id INTEGER REFERENCES chapters(id),
  chapter_no INTEGER,
  character_name TEXT NOT NULL,
  dialogue_count INTEGER DEFAULT 0,
  detected_dialect_pack TEXT DEFAULT '',
  dialect_hits_json TEXT DEFAULT '[]',
  meme_hits_json TEXT DEFAULT '[]',
  banned_meme_hits_json TEXT DEFAULT '[]',
  english_hits_json TEXT DEFAULT '[]',
  banned_english_hits_json TEXT DEFAULT '[]',
  forbidden_hits_json TEXT DEFAULT '[]',
  missing_signature_json TEXT DEFAULT '[]',
  narration_pollution_json TEXT DEFAULT '[]',
  profile_mismatch_json TEXT DEFAULT '[]',
  warning_count INTEGER DEFAULT 0,
  status TEXT DEFAULT 'PASS',
  report_json TEXT DEFAULT '{}',
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS character_voice_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  novel_id INTEGER NOT NULL REFERENCES novels(id),
  character_name TEXT NOT NULL,
  action TEXT NOT NULL,
  old_profile_json TEXT DEFAULT '{}',
  new_profile_json TEXT DEFAULT '{}',
  reason TEXT DEFAULT '',
  changed_by TEXT DEFAULT 'agent',
  changed_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_voice_profiles_novel_character
ON character_voice_profiles(novel_id, character_name);

CREATE INDEX IF NOT EXISTS idx_voice_observations_novel_chapter
ON character_voice_observations(novel_id, chapter_no);

CREATE INDEX IF NOT EXISTS idx_voice_observations_character
ON character_voice_observations(novel_id, character_name);

CREATE INDEX IF NOT EXISTS idx_voice_examples_character
ON character_voice_examples(novel_id, character_name);
