"""test_voice_memory_schema.py — 验证声纹相关表创建和 migration

v0.8.3 (M11): DB 路径走 tmp_db fixture（conftest.py），不再用 tempfile.mktemp。
"""

import sqlite3

from src.db.init_db import find_migrations, find_schema, init_db


def test_voice_tables_exist(tmp_db):
    """conftest 的 tmp_db 已经跑过 init_db，5 张声纹表应当全部存在。"""
    conn = sqlite3.connect(str(tmp_db))
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()

    expected = {
        "voice_packs", "character_voice_profiles",
        "character_voice_examples", "character_voice_observations",
        "character_voice_history", "schema_migrations",
    }
    missing = expected - tables
    assert not missing, f"Missing tables: {missing}"


def test_migration_idempotent(tmp_path, project_root):
    """对同一 DB 跑两次 init_db 不能炸。"""
    schema = find_schema(project_root / "tests")
    migrations = find_migrations(project_root / "tests")
    assert schema is not None, "Schema not found"

    db_path = tmp_path / "idempotent.db"
    assert init_db(db_path, schema, migrations)
    assert init_db(db_path, schema, migrations)
