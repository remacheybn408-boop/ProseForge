"""test_import_voice_packs.py — 验证 voice_packs 导入"""

import sqlite3, tempfile, os, sys
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from init_db import init_db, find_schema, find_migrations
from import_voice_packs import import_packs


def _setup_db():
    db_path = tempfile.mktemp(suffix=".db")
    base = Path(os.path.dirname(os.path.abspath(__file__))).parent
    schema = find_schema(base / "scripts")
    migrations = find_migrations(base / "scripts")
    init_db(db_path, schema, migrations)
    return db_path


def test_import_all_packs():
    """All voice_packs JSON files should import without error."""
    db_path = _setup_db()
    packs_dir = os.path.join(os.path.dirname(__file__), "..", "voice_packs")
    result = import_packs(db_path, packs_dir)
    assert result["ok"], f"Import errors: {result.get('errors', [])}"
    assert result["imported"] >= 10  # at least 10 packs


def test_shandong_pack_content():
    """Imported pack should have correct content."""
    db_path = _setup_db()
    packs_dir = os.path.join(os.path.dirname(__file__), "..", "voice_packs")
    import_packs(db_path, packs_dir)

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT markers_json, soft_markers_json FROM voice_packs WHERE pack_id='shandong_light'")
    row = cur.fetchone()
    assert row is not None, "shandong_light not found"
    markers = __import__("json").loads(row[0])
    assert "俺" in markers
    assert "甭" in markers
    conn.close()


def test_repeat_import_is_upsert():
    """Importing twice should update, not duplicate."""
    db_path = _setup_db()
    packs_dir = os.path.join(os.path.dirname(__file__), "..", "voice_packs")
    r1 = import_packs(db_path, packs_dir)
    r2 = import_packs(db_path, packs_dir)
    assert r2["imported"] == 0
    assert r2["updated"] >= 10
