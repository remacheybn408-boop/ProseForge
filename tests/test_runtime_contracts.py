from __future__ import annotations

import sqlite3
from pathlib import Path

from src.db.init_db import find_migrations, find_schema, init_db
from src.interfaces.cli import main


def test_config_example_matches_default_loader(project_root: Path):
    from src.utils.config_utils import load_default_config, load_json_config

    default_cfg = load_default_config(project_root)
    example_cfg = load_json_config(project_root / "config.example.json", project_root)
    assert default_cfg == example_cfg


def test_init_db_applies_real_migrations(tmp_path: Path, project_root: Path):
    db_path = tmp_path / "migrated.db"
    schema = find_schema(project_root / "tests")
    migrations = find_migrations(project_root / "tests")

    assert schema is not None
    assert migrations, "database/migrations should not be empty"
    assert init_db(db_path, schema, migrations)

    conn = sqlite3.connect(str(db_path))
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "arc_character_states" in tables
        assert "character_relationships" in tables

        applied = {
            row[0]
            for row in conn.execute("SELECT filename FROM schema_migrations")
        }
        assert {name for name, _ in migrations}.issubset(applied)
    finally:
        conn.close()


def test_legacy_cli_doctor(tmp_path: Path, capsys):
    code = main(["--project-root", str(tmp_path), "doctor"])
    assert code == 0
    assert '"status": "ok"' in capsys.readouterr().out
