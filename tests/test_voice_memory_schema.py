"""test_voice_memory_schema.py — 验证声纹相关表创建和 migration"""

import sqlite3, tempfile, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from init_db import init_db, find_schema, find_migrations


def test_voice_tables_exist():
    """After init_db, all 5 voice tables should exist."""
    db_path = tempfile.mktemp(suffix=".db")
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    schema = find_schema(script_dir.parent / "scripts")
    migrations = find_migrations(script_dir.parent / "scripts")

    assert schema is not None, "Schema not found"
    assert init_db(db_path, schema, migrations)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {r[0] for r in cur.fetchall()}

    expected = {
        "voice_packs", "character_voice_profiles",
        "character_voice_examples", "character_voice_observations",
        "character_voice_history", "schema_migrations",
    }
    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"
    conn.close()


def test_migration_idempotent():
    """Running init_db twice should not error."""
    db_path = tempfile.mktemp(suffix=".db")
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    schema = find_schema(script_dir.parent / "scripts")
    migrations = find_migrations(script_dir.parent / "scripts")

    assert init_db(db_path, schema, migrations)
    assert init_db(db_path, schema, migrations)  # second run
