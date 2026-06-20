"""Shared pytest fixtures for ProseForge tests.

v0.8.3 测试基建（AGENTS.md#M10）。新测试优先用这里的 fixture，避免
`tempfile.mktemp` / `mkdtemp` 散落各处（见 AGENTS.md#M11）。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def project_root() -> Path:
    """Repo root（D:/ProseForge）。给需要 schema.sql / packs / configs 的测试用。"""
    return _REPO_ROOT


@pytest.fixture
def tmp_db(tmp_path: Path, project_root: Path) -> Path:
    """初始化好 schema 的 sqlite 路径；自动随 tmp_path 清理。

    用 `src.db.init_db.init_db()` 跑 `database/schema.sql` + 任何 migrations。
    返回 Path（调用方自己 `sqlite3.connect(str(...))`）。
    """
    from src.db.init_db import find_migrations, find_schema, init_db

    schema = find_schema(project_root / "tests")
    migrations = find_migrations(project_root / "tests")
    assert schema is not None, (
        f"database/schema.sql not found from {project_root}; "
        "did codex remove it? See AGENTS.md#H9."
    )

    db_path = tmp_path / "test.db"
    assert init_db(db_path, schema, migrations), "init_db failed"
    return db_path
