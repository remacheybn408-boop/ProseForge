"""
test_slot_schema_heal.py — 遗留 slot DB 自愈到完整 schema

覆盖:
- SlotManager.ensure_slot_schema 把缺表的库补齐，且不丢既有数据
- src.db.init_db.schema_is_current / ensure_db_schema 的幂等与快路径
- pipeline._base.ensure_tables 在缺表时触发全 schema 自愈
"""
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.db.slot_manager import SlotManager
from src.db.init_db import schema_is_current, ensure_db_schema, expected_table_names
from src.pipeline._base import ensure_tables

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def project_root(tmp_path):
    """临时项目根，带上真实 database/（schema.sql + migrations），模拟 clone。"""
    root = tmp_path / "proj"
    root.mkdir()
    shutil.copytree(REPO / "database", root / "database")
    return root


def _tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    finally:
        conn.close()


def _make_slot(project_root: Path, slot_id: str = "s1") -> tuple[SlotManager, Path]:
    mgr = SlotManager(project_root)
    mgr.init_workspace()
    mgr.create_slot(slot_id, ensure_registry=True, name="t", description="t")
    return mgr, mgr.get_slot_db_path(slot_id)


def test_ensure_slot_schema_heals_missing_table_without_data_loss(project_root):
    mgr, db = _make_slot(project_root)

    # 种一行数据，证明补齐不丢数据
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO novels(slug, title) VALUES('x', 'y')")
    conn.commit()
    conn.close()

    before = _tables(db)
    assert "writing_rules" in before

    # 模拟遗留库：删掉一张表
    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE writing_rules")
    conn.commit()
    conn.close()

    assert "writing_rules" not in _tables(db)
    assert schema_is_current(db, project_root) is False

    assert mgr.ensure_slot_schema("s1") is True

    after = _tables(db)
    assert "writing_rules" in after
    assert schema_is_current(db, project_root) is True
    # 非破坏性：原有表一张不少
    assert before <= after
    # 数据保留
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT slug FROM novels").fetchone()[0] == "x"
    conn.close()


def test_ensure_db_schema_fastpath_noop_when_current(project_root):
    _mgr, db = _make_slot(project_root)
    # 刚建的库已是最新 → 快路径返回 True，不报错
    assert schema_is_current(db, project_root) is True
    assert ensure_db_schema(db, project_root) is True
    # 期望表全在
    assert expected_table_names(project_root) <= _tables(db)


def test_ensure_db_schema_missing_db_returns_false(project_root):
    missing = project_root / "workspace" / "nope" / "novel.db"
    assert ensure_db_schema(missing, project_root) is False


def test_ensure_tables_self_heals_partial_db(project_root):
    _mgr, db = _make_slot(project_root)

    conn = sqlite3.connect(db)
    conn.execute("DROP TABLE writing_rules")
    conn.commit()
    conn.close()
    assert "writing_rules" not in _tables(db)

    # 用最小 ctx 触发 pipeline 入口自愈（ensure_tables 只读 project_root/db_path）
    ctx = SimpleNamespace(project_root=project_root, db_path=db)
    ensure_tables(ctx)

    assert "writing_rules" in _tables(db)
    assert schema_is_current(db, project_root) is True
