#!/usr/bin/env python3
"""
fts_health.py — FTS5 Health Check, Rebuild, and Fallback Retrieval v0.4.5

Problem: FTS5 indexes corrupt (invalid fts5 file format) and the engine
only prints a WARN, continuing with broken full-text search. Over time,
context retrieval goes empty and chapters drift.

Solution:
  - check_fts_health: verify all FTS5 tables are readable
  - rebuild_fts: attempt rebuild; recreate from schema if rebuild fails
  - safe_fts_search: try FTS5, rebuild on failure, fallback to LIKE
"""

import sqlite3
import json
import os
from pathlib import Path
from typing import Optional


def _get_db_path(config: dict = None) -> str:
    """Resolve DB path from config, env var, or project-relative default.

    Resolution order:
      1. config['db_path'] — if provided in config dict
      2. HERMES_MEMORY_DB env var
      3. <project_root>/data/novel_memory.db — project-relative (cross-platform)
      4. ~/.novel-pipeline/hermes_memory.db — user home fallback
    """
    if config:
        db = config.get("db_path", "")
        if db:
            return db
    # Check environment variable
    env_db = os.environ.get("HERMES_MEMORY_DB", "")
    if env_db:
        return env_db
    # Project-relative default (does not depend on project_root import)
    project_db = Path(__file__).resolve().parent.parent / "data" / "novel_memory.db"
    if project_db.exists():
        return str(project_db)
    # User home fallback
    return str(Path.home() / ".novel-pipeline" / "hermes_memory.db")


def find_fts5_tables(conn: sqlite3.Connection) -> list[str]:
    """Find all FTS5 virtual tables in the database."""
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND sql LIKE '%USING fts5%'")
    return [row[0] for row in c.fetchall()]


def check_fts_health(config: dict = None) -> dict:
    """
    Check all FTS5 tables for corruption.
    Returns {"ok": True} or {"ok": False, "table": ..., "error": ...}
    """
    db_path = _get_db_path(config)
    if not Path(db_path).exists():
        return {"ok": False, "error": f"DB not found: {db_path}"}

    try:
        conn = sqlite3.connect(db_path)
        tables = find_fts5_tables(conn)
        broken = []

        for table in tables:
            try:
                # Basic read test
                conn.execute(f"SELECT rowid FROM {table} LIMIT 1").fetchall()
                # Search test
                conn.execute(
                    f"SELECT rowid FROM {table} WHERE {table} MATCH ? LIMIT 1",
                    ("test",)).fetchall()
            except sqlite3.DatabaseError as e:
                broken.append({"table": table, "error": str(e)})

        conn.close()

        if broken:
            return {"ok": False, "broken_tables": broken,
                    "broken_count": len(broken),
                    "total_tables": len(tables)}
        return {"ok": True, "total_tables": len(tables),
                "all_healthy": True}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def _get_fts_schema(conn: sqlite3.Connection, table: str) -> Optional[str]:
    """Get the CREATE VIRTUAL TABLE statement for an FTS table."""
    c = conn.cursor()
    c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,))
    row = c.fetchone()
    return row[0] if row else None


def rebuild_fts(config: dict = None) -> dict:
    """
    Attempt to rebuild all FTS5 indexes.
    Strategy:
      1. Try INSERT ... VALUES('rebuild') for each table
      2. If that fails, drop and recreate from schema
    Returns repair report.
    """
    db_path = _get_db_path(config)
    if not Path(db_path).exists():
        return {"ok": False, "error": f"DB not found: {db_path}"}

    conn = sqlite3.connect(db_path)
    tables = find_fts5_tables(conn)
    repaired = []
    failed = []

    for table in tables:
        try:
            conn.execute(f"INSERT INTO {table}({table}) VALUES('rebuild')")
            conn.commit()
            repaired.append({"table": table, "method": "rebuild"})
        except sqlite3.DatabaseError:
            # rebuild failed — try drop + recreate
            try:
                schema = _get_fts_schema(conn, table)
                if schema:
                    conn.execute(f"DROP TABLE IF EXISTS {table}")
                    conn.execute(schema)
                    conn.commit()
                    repaired.append({"table": table, "method": "recreate"})
                else:
                    failed.append({"table": table, "error": "no schema found"})
            except sqlite3.DatabaseError as e2:
                failed.append({"table": table, "error": str(e2)})

    conn.close()

    return {
        "ok": len(failed) == 0,
        "repaired": repaired,
        "failed": failed,
        "repaired_count": len(repaired),
        "failed_count": len(failed),
    }


def safe_fts_search(query: str, config: dict = None,
                    table: str = "novel_chapter_fts",
                    columns: str = "content",
                    limit: int = 20,
                    fallback: bool = True) -> dict:
    """
    Execute FTS5 search with auto-repair and LIKE fallback.

    Returns:
      {"ok": True, "results": [...], "method": "fts5"|"rebuild"|"like"}
    """
    db_path = _get_db_path(config)
    if not Path(db_path).exists():
        return {"ok": False, "error": "DB not found", "results": []}

    conn = sqlite3.connect(db_path)

    # Try FTS5 first
    try:
        c = conn.cursor()
        c.execute(
            f"SELECT {columns} FROM {table} WHERE {table} MATCH ? LIMIT ?",
            (query, limit))
        results = c.fetchall()
        conn.close()
        return {"ok": True, "results": results, "method": "fts5"}
    except sqlite3.DatabaseError as e:
        if "fts5" not in str(e).lower() or not fallback:
            conn.close()
            return {"ok": False, "error": str(e), "results": []}

    # FTS5 broken — try rebuild then retry
    rebuild_result = rebuild_fts(config)
    conn2 = sqlite3.connect(db_path)
    try:
        c2 = conn2.cursor()
        c2.execute(
            f"SELECT {columns} FROM {table} WHERE {table} MATCH ? LIMIT ?",
            (query, limit))
        results = c2.fetchall()
        conn2.close()
        return {"ok": True, "results": results, "method": "rebuild"}
    except sqlite3.DatabaseError:
        conn2.close()

    # FTS5 still broken — LIKE fallback on content table
    # FTS5 virtual tables don't support LIKE; query the content table instead
    _FTS_TO_CONTENT = {
        "novel_chapter_fts": "chapters",
        "novel_chunk_fts": "chapter_chunks",
        "novel_character_fts": "characters",
        "novel_world_fts": "worldbuilding",
        "novel_plot_fts": "plot_threads",
        "memory_fts": "memories",
    }
    content_table = _FTS_TO_CONTENT.get(table, table)
    try:
        conn3 = sqlite3.connect(db_path)
        c3 = conn3.cursor()
        # Split query into words for LIKE matching
        words = query.split()
        conditions = " AND ".join([f"{columns} LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words]
        c3.execute(
            f"SELECT {columns} FROM {content_table} WHERE {conditions} LIMIT ?",
            (*params, limit))
        results = c3.fetchall()
        conn3.close()
        return {"ok": True, "results": results, "method": "like_fallback"}
    except Exception as e3:
        return {"ok": False, "error": str(e3), "results": [], "method": "like_fallback"}


def ensure_fts_healthy(config: dict = None) -> dict:
    """
    Check FTS health and repair if needed. Call before pre/post.
    Returns final health status.
    """
    health = check_fts_health(config)
    if health["ok"]:
        return {"action": "none", "health": health}

    repair = rebuild_fts(config)
    health2 = check_fts_health(config)
    return {
        "action": "repaired" if repair["ok"] else "repair_failed",
        "health_before": health,
        "repair": repair,
        "health_after": health2,
    }


# ═══════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser(description="FTS5 Health Tool")
    parser.add_argument("--config", default=None, help="config.json path")
    parser.add_argument("--check", action="store_true", help="Run health check")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild all FTS5 indexes")
    parser.add_argument("--ensure", action="store_true", help="Check + repair if needed")
    parser.add_argument("--search", default=None, help="Test search query")
    args = parser.parse_args()

    config = {}
    if args.config:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))

    if args.check:
        result = check_fts_health(config)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.rebuild:
        result = rebuild_fts(config)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.ensure:
        result = ensure_fts_healthy(config)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    elif args.search:
        result = safe_fts_search(args.search, config)
        print(json.dumps(result, ensure_ascii=False, indent=2))

    else:
        # Default: check only
        result = check_fts_health(config)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
