#!/usr/bin/env python3
"""
fts5_retriever.py — FTS5 全文检索增强器

在现有 fts_health.py 的安全搜索基础上，提供:
  - 章节级 + 分块级 FTS5 检索
  - 结果元数据补全 (title, chapter_no, score)
  - 结构化输出 (带 evidence 出处)

依赖: scripts/fts_health.py (已有模块)
"""

import sqlite3
import sys
from pathlib import Path
from typing import Optional

# 将 scripts 目录加入 path 以便导入 fts_health
_SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from fts_health import safe_fts_search


def _enrich_chapter_results(conn: sqlite3.Connection, rowids: list[int]) -> list[dict]:
    """
    根据章节 rowid 列表，补全 title / chapter_no 等元数据。

    Args:
        conn: 数据库连接
        rowids: chapters 表的 id 列表

    Returns:
        list[dict]: 每项含 {chapter_id, chapter_no, title, content_snippet}
    """
    if not rowids:
        return []

    placeholders = ",".join("?" * len(rowids))
    cur = conn.cursor()
    cur.execute(
        f"""SELECT id, chapter_no, title,
                   substr(content, 1, 300) AS snippet
            FROM chapters WHERE id IN ({placeholders})""",
        rowids,
    )
    rows = cur.fetchall()
    results = []
    for row in rows:
        results.append({
            "chapter_id": row[0],
            "chapter_no": row[1],
            "title": row[2],
            "evidence": row[3],
        })
    return results


def _enrich_chunk_results(conn: sqlite3.Connection, rowids: list[int]) -> list[dict]:
    """
    根据 chunk rowid 列表，补全所属章节元数据。

    Args:
        conn: 数据库连接
        rowids: chapter_chunks 表的 id 列表

    Returns:
        list[dict]: 每项含 {chunk_id, chapter_id, chapter_no, chunk_no, title, evidence}
    """
    if not rowids:
        return []

    placeholders = ",".join("?" * len(rowids))
    cur = conn.cursor()
    cur.execute(
        f"""SELECT cc.id, cc.chapter_id, cc.chunk_no, cc.content,
                   ch.chapter_no, ch.title
            FROM chapter_chunks cc
            JOIN chapters ch ON ch.id = cc.chapter_id
            WHERE cc.id IN ({placeholders})""",
        rowids,
    )
    rows = cur.fetchall()
    results = []
    for row in rows:
        results.append({
            "chunk_id": row[0],
            "chapter_id": row[1],
            "chunk_no": row[2],
            "evidence": row[3][:300],
            "chapter_no": row[4],
            "title": row[5],
        })
    return results


def search_chapters(
    query: str,
    db_path: str,
    top_k: int = 5,
    enrich: bool = True,
) -> dict:
    """
    在章节级别执行 FTS5 检索。

    Args:
        query: 查询文本
        db_path: SQLite 数据库路径
        top_k: 返回结果数
        enrich: 是否补全章节元数据

    Returns:
        dict: {
            "status": "ok" | "error",
            "results": [{chapter_id, chapter_no, title, evidence, score, source}, ...],
            "method": "fts5" | "rebuild" | "like_fallback",
        }
    """
    config = {"db_path": db_path}
    result = safe_fts_search(
        query=query,
        config=config,
        table="novel_chapter_fts",
        columns="rowid",
        limit=top_k * 2,  # 多取一些供后续 score 排序
    )

    if not result.get("ok"):
        return {
            "status": "error",
            "results": [],
            "error": result.get("error", "FTS5 search failed"),
            "method": result.get("method", "unknown"),
        }

    rowids = [r[0] for r in result.get("results", [])]

    # 补全元数据
    enriched = []
    if enrich and rowids:
        try:
            conn = sqlite3.connect(db_path)
            enriched = _enrich_chapter_results(conn, rowids[:top_k])
            conn.close()
        except Exception as e:
            # 降级: 只返回 rowid
            enriched = [{"chapter_id": rid, "evidence": "", "source": "fts5"} for rid in rowids[:top_k]]

    if not enriched and rowids:
        enriched = [{"chapter_id": rid, "evidence": "", "source": "fts5"} for rid in rowids[:top_k]]

    # 附加 source 和 score 信息
    for item in enriched:
        item["source"] = "fts5"
        item["score"] = 1.0  # FTS5 默认相关性由 BM25 决定，此处统一标记

    return {
        "status": "ok",
        "results": enriched,
        "method": result.get("method", "fts5"),
    }


def search_chunks(
    query: str,
    db_path: str,
    top_k: int = 10,
    enrich: bool = True,
) -> dict:
    """
    在分块级别执行 FTS5 检索 (更细粒度)。

    Args:
        query: 查询文本
        db_path: SQLite 数据库路径
        top_k: 返回结果数
        enrich: 是否补全所属章节元数据

    Returns:
        dict: {
            "status": "ok" | "error",
            "results": [{chunk_id, chapter_id, chunk_no, chapter_no, title, evidence, score, source}, ...],
            "method": "fts5" | "rebuild" | "like_fallback",
        }
    """
    config = {"db_path": db_path}
    result = safe_fts_search(
        query=query,
        config=config,
        table="novel_chunk_fts",
        columns="rowid",
        limit=top_k * 2,
    )

    if not result.get("ok"):
        return {
            "status": "error",
            "results": [],
            "error": result.get("error", "FTS5 chunk search failed"),
            "method": result.get("method", "unknown"),
        }

    rowids = [r[0] for r in result.get("results", [])]

    enriched = []
    if enrich and rowids:
        try:
            conn = sqlite3.connect(db_path)
            enriched = _enrich_chunk_results(conn, rowids[:top_k])
            conn.close()
        except Exception:
            enriched = [{"chunk_id": rid, "evidence": "", "source": "fts5_chunk"} for rid in rowids[:top_k]]

    if not enriched and rowids:
        enriched = [{"chunk_id": rid, "evidence": "", "source": "fts5_chunk"} for rid in rowids[:top_k]]

    for item in enriched:
        item["source"] = "fts5_chunk"
        item["score"] = 1.0

    return {
        "status": "ok",
        "results": enriched,
        "method": result.get("method", "fts5"),
    }
