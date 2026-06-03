"""test_voice_profile_loader.py — 验证声纹加载优先级"""

import sqlite3, tempfile, os, sys, json
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from init_db import init_db, find_schema, find_migrations
from import_voice_packs import import_packs
from import_voice_profiles import import_profiles
from voice_profile_loader import load_voice_context, get_profiles_for_characters


def _setup_db():
    db_path = tempfile.mktemp(suffix=".db")
    base = Path(os.path.dirname(os.path.abspath(__file__))).parent
    schema = find_schema(base / "scripts")
    migrations = find_migrations(base / "scripts")
    init_db(db_path, schema, migrations)

    # Create a demo novel
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT INTO novels(slug, title) VALUES(?,?)", ("demo_novel", "Demo Novel"))
    conn.execute("INSERT INTO characters(novel_id, name, role) VALUES(1, '理工主角', 'protagonist')")
    conn.execute("INSERT INTO characters(novel_id, name, role) VALUES(1, '好兄弟', 'supporting')")
    conn.execute("INSERT INTO characters(novel_id, name, role) VALUES(1, '古修长老', 'supporting')")
    conn.commit()
    conn.close()

    # Import packs
    import_packs(db_path, str(base / "voice_packs"))
    return db_path


def test_loader_reads_from_db():
    """Loader should read profiles from database when available."""
    db_path = _setup_db()
    base = Path(os.path.dirname(os.path.abspath(__file__))).parent

    # Import profiles into DB
    example_path = str(base / "examples" / "demo_novel" / "voice_profiles.example.json")
    result = import_profiles(db_path, "demo_novel", example_path)
    assert result["ok"], f"Import failed: {result}"

    # Load via loader
    config = {
        "voice_system": {"enabled": True, "use_database_profiles": True},
        "db_path": db_path,
    }
    ctx = load_voice_context(config, "demo_novel", db_path=db_path)
    assert ctx["source"] == "db"
    assert len(ctx["profiles"]) >= 5
    assert len(ctx["packs"]) >= 10


def test_get_profiles_for_characters():
    """Should filter profiles to requested characters."""
    db_path = _setup_db()
    example_path = os.path.join(os.path.dirname(__file__), "..",
                                "examples", "demo_novel", "voice_profiles.example.json")
    import_profiles(db_path, "demo_novel", example_path)
    config = {"voice_system": {"enabled": True, "use_database_profiles": True}, "db_path": db_path}
    ctx = load_voice_context(config, "demo_novel", db_path=db_path,
                             character_names=["理工主角", "好兄弟"])
    assert len(ctx["profiles"]) == 2
    names = {p["character_name"] for p in ctx["profiles"]}
    assert names == {"理工主角", "好兄弟"}


def test_protagonist_no_dialect():
    """理工主角 must have dialect_level=0 and no dialect pack."""
    db_path = _setup_db()
    example_path = os.path.join(os.path.dirname(__file__), "..",
                                "examples", "demo_novel", "voice_profiles.example.json")
    import_profiles(db_path, "demo_novel", example_path)
    config = {"voice_system": {"enabled": True, "use_database_profiles": True}, "db_path": db_path}
    ctx = load_voice_context(config, "demo_novel", db_path=db_path,
                             character_names=["理工主角"])
    lg = ctx["profiles"][0]
    assert lg["dialect_level"] == 0
    assert lg["meme_level"] == 0
    assert lg["dialect_pack"] == "none"
