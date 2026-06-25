from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from src.db.init_db import find_migrations, find_schema, init_db
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


def test_nf_pipeline_cli_accepts_rewrite_and_accept(project_root: Path):
    """rewrite/accept 是合法 action（产改写卡 / diff+入库），且要求必填参数。

    重新引入改写闭环后契约变更：不再拒绝 rewrite，而是要求 slug/title/vol-no/chapter-no。
    """
    script = project_root / "plugin" / "proseforge-codex" / "scripts" / "nf_pipeline.py"
    for action in ("rewrite", "accept"):
        result = subprocess.run(
            [sys.executable, str(script), "--action", action],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        combined = f"{result.stdout}\n{result.stderr}"
        # action 被识别（不是 invalid choice），但缺参数时报 missing required arguments
        assert "invalid choice" not in combined
        assert result.returncode != 0
        assert "missing required arguments" in combined
        assert action in combined
