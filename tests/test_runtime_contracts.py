from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from src.db.init_db import find_migrations, find_schema, init_db
from src.report.html_report_builder import get_db_path as get_html_db_path, load_config as load_html_config
from src.utils.config_utils import load_default_config, load_json_config


def test_config_example_matches_default_loader(project_root: Path):
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


def test_html_report_builder_resolves_config_relative_db_path(tmp_path: Path, project_root: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text('{"db_path":"./data/custom.db"}', encoding="utf-8")
    cfg = load_html_config(str(config_path))
    assert get_html_db_path(cfg).endswith(str(Path("data") / "custom.db"))


def test_nf_pipeline_cli_no_longer_accepts_rewrite(project_root: Path):
    script = project_root / "plugin" / "proseforge-codex" / "scripts" / "nf_pipeline.py"
    result = subprocess.run(
        [sys.executable, str(script), "--action", "rewrite"],
        cwd=project_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "rewrite" in combined
    assert "invalid choice" in combined or "unsupported action" in combined
