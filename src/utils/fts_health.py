#!/usr/bin/env python3
"""FTS5 health, repair, and fallback retrieval helpers."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from src.utils.config_utils import find_project_root, resolve_path
from src.db._conn import connect_sqlite


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _safe_ident(identifier: str) -> str:
    """校验 SQL 标识符（表名/列名，列名可逗号分隔）只含 [A-Za-z0-9_]。

    本模块用 f-string 拼表名/列名（FTS5 的 MATCH 语法无法对标识符用占位符）。
    当前调用方均来自 sqlite_master 枚举或内部白名单，无注入风险——此护栏把
    "输入可信"的隐含假设变成显式断言，防止将来接入外部输入时被滥用。
    """
    for part in identifier.split(","):
        if not _IDENT_RE.match(part.strip()):
            raise ValueError(f"unsafe SQL identifier: {identifier!r}")
    return identifier


def _get_db_path(config: dict | None = None) -> Path:
    if config and config.get("db_path"):
        return Path(config["db_path"])
    project_root = find_project_root(Path(__file__).resolve())
    return resolve_path(project_root, "./data/novel_memory.db")


def find_fts5_tables(conn: sqlite3.Connection) -> list[str]:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%USING fts5%'")
    # 表名来自 sqlite_master，仍过一遍 _safe_ident 把可信假设变显式护栏（覆盖下游所有 {table} 插值）。
    return [_safe_ident(row[0]) for row in cur.fetchall()]


def check_fts_health(config: dict | None = None) -> dict:
    db_path = _get_db_path(config)
    if not db_path.exists():
        return {
            "ok": False,
            "status": "db_missing",
            "db_path": str(db_path),
            "total_tables": 0,
            "broken_tables": [],
        }

    try:
        conn = connect_sqlite(db_path)
        tables = find_fts5_tables(conn)
        broken = []
        progress = []

        for index, table in enumerate(tables, start=1):
            try:
                conn.execute(f"SELECT rowid FROM {table} LIMIT 1").fetchall()
                conn.execute(f"SELECT rowid FROM {table} WHERE {table} MATCH ? LIMIT 1", ("test",)).fetchall()
                progress.append({"table": table, "index": index, "status": "healthy"})
            except sqlite3.DatabaseError as exc:
                broken.append({"table": table, "error": str(exc), "index": index})
                progress.append({"table": table, "index": index, "status": "broken", "error": str(exc)})
        conn.close()
        if broken:
            return {
                "ok": False,
                "status": "broken",
                "db_path": str(db_path),
                "total_tables": len(tables),
                "broken_count": len(broken),
                "broken_tables": broken,
                "progress": progress,
            }
        return {
            "ok": True,
            "status": "healthy",
            "db_path": str(db_path),
            "total_tables": len(tables),
            "broken_count": 0,
            "broken_tables": [],
            "progress": progress,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "db_path": str(db_path),
            "total_tables": 0,
            "broken_tables": [],
            "error": str(exc),
            "progress": [],
        }


def _get_fts_schema(conn: sqlite3.Connection, table: str) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
    row = cur.fetchone()
    return row[0] if row else None


def rebuild_fts(config: dict | None = None) -> dict:
    db_path = _get_db_path(config)
    if not db_path.exists():
        return {
            "ok": False,
            "status": "db_missing",
            "db_path": str(db_path),
            "total_tables": 0,
            "repaired": [],
            "failed": [],
            "progress": [],
            "repaired_count": 0,
            "failed_count": 0,
        }

    conn = connect_sqlite(db_path)
    tables = find_fts5_tables(conn)
    repaired = []
    failed = []
    progress = []

    for index, table in enumerate(tables, start=1):
        step = {"table": table, "index": index, "total_tables": len(tables)}
        try:
            conn.execute(f"INSERT INTO {table}({table}) VALUES('rebuild')")
            conn.commit()
            repaired.append({"table": table, "method": "rebuild", "index": index})
            progress.append({**step, "status": "repaired", "method": "rebuild"})
        except sqlite3.DatabaseError:
            try:
                schema = _get_fts_schema(conn, table)
                if not schema:
                    raise sqlite3.DatabaseError("no schema found")
                conn.execute(f"DROP TABLE IF EXISTS {table}")
                conn.execute(schema)
                conn.commit()
                repaired.append({"table": table, "method": "recreate", "index": index})
                progress.append({**step, "status": "repaired", "method": "recreate"})
            except sqlite3.DatabaseError as exc:
                failed.append({"table": table, "error": str(exc), "index": index})
                progress.append({**step, "status": "failed", "method": "recreate", "error": str(exc)})
    conn.close()

    return {
        "ok": not failed,
        "status": "repaired" if not failed else "repair_failed",
        "db_path": str(db_path),
        "total_tables": len(tables),
        "repaired": repaired,
        "failed": failed,
        "progress": progress,
        "repaired_count": len(repaired),
        "failed_count": len(failed),
    }


def safe_fts_search(
    query: str,
    config: dict | None = None,
    table: str = "novel_chapter_fts",
    columns: str = "content",
    limit: int = 20,
    fallback: bool = True,
) -> dict:
    db_path = _get_db_path(config)
    if not db_path.exists():
        return {"ok": False, "error": "DB not found", "results": [], "method": "db_missing"}

    # table/columns 是函数参数（内部调用方传入白名单值）——拼接前显式校验。
    _safe_ident(table)
    _safe_ident(columns)

    conn = connect_sqlite(db_path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {columns} FROM {table} WHERE {table} MATCH ? LIMIT ?", (query, limit))
        return {"ok": True, "results": cur.fetchall(), "method": "fts5"}
    except sqlite3.DatabaseError as exc:
        if "fts5" not in str(exc).lower() or not fallback:
            return {"ok": False, "error": str(exc), "results": [], "method": "fts5"}
    finally:
        conn.close()

    rebuild_result = rebuild_fts(config)
    conn = connect_sqlite(db_path)
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT {columns} FROM {table} WHERE {table} MATCH ? LIMIT ?", (query, limit))
        return {
            "ok": True,
            "results": cur.fetchall(),
            "method": "rebuild",
            "repair": rebuild_result,
        }
    except sqlite3.DatabaseError:
        pass
    finally:
        conn.close()

    content_table = _safe_ident({
        "novel_chapter_fts": "chapters",
        "novel_chunk_fts": "chapter_chunks",
        "novel_character_fts": "characters",
        "novel_world_fts": "worldbuilding",
        "novel_plot_fts": "plot_threads",
        "memory_fts": "memories",
    }.get(table, table))

    try:
        conn = connect_sqlite(db_path)
        cur = conn.cursor()
        words = query.split()
        conditions = " AND ".join([f"{columns} LIKE ?" for _ in words]) or "1=1"
        params = [f"%{word}%" for word in words]
        cur.execute(f"SELECT {columns} FROM {content_table} WHERE {conditions} LIMIT ?", (*params, limit))
        return {
            "ok": True,
            "results": cur.fetchall(),
            "method": "like_fallback",
            "repair": rebuild_result,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "results": [], "method": "like_fallback", "repair": rebuild_result}
    finally:
        try:
            conn.close()
        except Exception:
            pass


def ensure_fts_healthy(config: dict | None = None) -> dict:
    health_before = check_fts_health(config)
    if health_before["ok"]:
        return {
            "action": "none",
            "health_before": health_before,
            "health_after": health_before,
            "repair": {
                "ok": True,
                "status": "not_needed",
                "total_tables": health_before.get("total_tables", 0),
                "progress": [],
                "repaired_count": 0,
                "failed_count": 0,
            },
        }

    repair = rebuild_fts(config)
    health_after = check_fts_health(config)
    return {
        "action": "repaired" if repair["ok"] and health_after["ok"] else "repair_failed",
        "health_before": health_before,
        "repair": repair,
        "health_after": health_after,
    }
