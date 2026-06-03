"""
test_schema_init.py — Schema 初始化测试
"""
import pytest
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import init_db
from pathlib import Path


class TestSchemaInit:
    def test_init_creates_db(self):
        """init_db creates database file"""
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            schema_path = Path(__file__).parent.parent / "database" / "schema.sql"

            result = init_db.init_db(str(db_path), str(schema_path), [])
            assert result == True
            assert db_path.exists()
            assert db_path.stat().st_size > 0

    def test_tables_exist(self):
        """All required tables are created"""
        import sqlite3
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            schema_path = Path(__file__).parent.parent / "database" / "schema.sql"

            init_db.init_db(str(db_path), str(schema_path), [])

            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '%_fts_%' ORDER BY name")
            tables = [r[0] for r in cur.fetchall()]

            required = ["novels", "chapters", "characters", "worldbuilding",
                       "volume_plans", "chapter_plans", "title_history",
                       "chapter_versions", "reader_promises"]
            for t in required:
                assert t in tables, f"Missing table: {t}"
            conn.close()
