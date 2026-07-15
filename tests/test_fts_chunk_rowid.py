"""
test_fts_chunk_rowid.py — High #2/#4 回归

#2: novel_chunk_fts(外部内容表) 的 rowid 必须 == chapter_chunks.id，否则
    _enrich_chunk_results 命中不到、rebuild 又会覆盖本地写。
#4: registry/slot 的 JSON 写走 write_json_atomic（原子、无残留 .tmp）。
"""
import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from src.db import init_db
from src.pipeline._base import App
from src.pipeline.ingest import ingest
from src.rag.fts5_retriever import _enrich_chunk_results
from src.db._conn import connect_sqlite


def _chapter_text() -> str:
    para = (
        "灵矿深处的风带着铁锈味。他握紧矿灯，一步一步往下走，脚下的石阶湿滑。"
        "远处传来滴水声，回荡在空旷的巷道里，像有人在低声数着什么。"
    )
    return "\n".join(para for _ in range(60)) + "\n本章自检:测试"


@pytest.fixture
def ingest_env(tmp_path, project_root, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = {
        "db_path": str(tmp_path / "data" / "novel.db"),
        "novels_root": str(tmp_path / "novels"),
        "exports_root": str(tmp_path / "exports"),
        "word_count": {"hard_min": 50, "ideal_min": 100, "ideal_max": 9000,
                       "normal_max": 99999, "special_max": 99999},
    }
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    schema = project_root / "database" / "schema.sql"
    init_db.init_db(cfg["db_path"], str(schema), [])

    slug = "test_novel"
    ts = "2025-01-01 00:00:00"
    conn = sqlite3.connect(cfg["db_path"])
    conn.execute("INSERT INTO novels(slug,title,genre,status) VALUES(?,?,?,?)",
                 (slug, "测试小说", "玄幻", "writing"))
    nid = conn.execute("SELECT id FROM novels WHERE slug=?", (slug,)).fetchone()[0]
    conn.execute("""INSERT INTO volume_plans(novel_id, volume_no, planned_title, volume_goal, updated_at)
                    VALUES(?,?,?,?,?)""", (nid, 1, "第一卷", "开篇", ts))
    conn.execute("""INSERT INTO chapter_plans(novel_id, volume_no, chapter_no, planned_title, chapter_goal, updated_at)
                    VALUES(?,?,?,?,?,?)""", (nid, 1, 1, "测试章", "开篇", ts))
    conn.commit()
    conn.close()

    chapters_dir = tmp_path / "novels" / slug / "第01卷"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    app = App(cfg, slug, "测试小说", 1, str(chapters_dir))
    return {"cfg": cfg, "app": app, "chapters_dir": chapters_dir, "slug": slug}


def _base_and_fts(db_path) -> tuple[set, set]:
    conn = sqlite3.connect(db_path)
    base = {r[0] for r in conn.execute("SELECT id FROM chapter_chunks")}
    fts = {r[0] for r in conn.execute("SELECT rowid FROM novel_chunk_fts")}
    conn.close()
    return base, fts


def test_chunk_fts_rowid_aligns_to_base_id(ingest_env):
    env = ingest_env
    (env["chapters_dir"] / "第1章_测试.txt").write_text(_chapter_text(), encoding="utf-8")
    ingest(1, "normal", app_inst=env["app"])

    base, fts = _base_and_fts(env["app"].db_path)
    assert base, "expected chapter_chunks rows"
    assert fts, "expected novel_chunk_fts rows"
    # 每个 FTS rowid 都是真实 chunk id（外部内容契约对齐）
    assert fts == base
    # 不再是合成 rowid（ch_id*10000+cno 会 >= 10000）
    assert all(rid < 10000 for rid in fts)


def test_stored_fts_rowids_enrich_nonempty(ingest_env):
    """FTS 里存的 rowid 必须能在 chapter_chunks 富化出非空 evidence（修复前恒空）。"""
    env = ingest_env
    (env["chapters_dir"] / "第1章_测试.txt").write_text(_chapter_text(), encoding="utf-8")
    ingest(1, "normal", app_inst=env["app"])

    conn = connect_sqlite(str(env["app"].db_path))
    fts_rowids = [r[0] for r in conn.execute("SELECT rowid FROM novel_chunk_fts LIMIT 5")]
    enriched = _enrich_chunk_results(conn, fts_rowids)
    conn.close()
    assert fts_rowids
    assert len(enriched) == len(fts_rowids)
    assert all(e["evidence"] for e in enriched)


def test_reingest_no_orphan_or_dup_fts(ingest_env):
    env = ingest_env
    f = env["chapters_dir"] / "第1章_测试.txt"
    f.write_text(_chapter_text(), encoding="utf-8")
    ingest(1, "normal", app_inst=env["app"])
    ingest(1, "normal", app_inst=env["app"])  # 重灌

    base, fts = _base_and_fts(env["app"].db_path)
    assert base and fts
    # 重灌后仍一一对齐，无孤儿、无重复
    assert fts == base


def test_reingest_same_content_is_idempotent(ingest_env):
    env = ingest_env
    f = env["chapters_dir"] / "第1章_测试.txt"
    f.write_text(_chapter_text(), encoding="utf-8")
    ingest(1, "normal", app_inst=env["app"])
    result = ingest(1, "normal", app_inst=env["app"])

    assert result["status"] == "noop"
    conn = connect_sqlite(str(env["app"].db_path))
    versions = conn.execute(
        "SELECT COUNT(*) FROM chapter_versions WHERE chapter_no=1"
    ).fetchone()[0]
    conn.close()
    assert versions == 1


def test_registry_slot_json_atomic_no_tmp(tmp_path, project_root):
    """#4: SlotManager 经 write_json_atomic 写 registry/project.json，无残留 .tmp。"""
    from src.db.slot_manager import SlotManager

    root = tmp_path / "proj"
    root.mkdir()
    shutil.copytree(project_root / "database", root / "database")

    mgr = SlotManager(root)
    mgr.init_workspace()
    mgr.create_slot("s1", ensure_registry=True, name="测试", description="测试")

    reg = root / "workspace" / "registry.json"
    proj = root / "workspace" / "s1" / "project.json"
    assert json.loads(reg.read_text(encoding="utf-8"))["slots"]
    assert json.loads(proj.read_text(encoding="utf-8"))["name"] == "测试"
    assert not list(root.rglob("*.tmp")), "原子写不应留下 .tmp 文件"
