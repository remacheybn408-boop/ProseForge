#!/usr/bin/env python3
"""Vector index management for RAG collections."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .rag_config import get_db_path, get_vector_config, load_rag_config
from .vector_retriever import HAS_VECTOR_DEPS, VectorRetriever
from src.db._conn import connect_sqlite

WORLD_BUILDING_COLLECTION = "novel_worldbuilding"


def _query_rows(db_path: str, sql: str) -> list[dict]:
    conn = connect_sqlite(db_path)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.cursor()
        cur.execute(sql)
        return [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()


def _get_all_chunks(db_path: str) -> list[dict]:
    return _query_rows(
        db_path,
        """
        SELECT cc.id, cc.chunk_no, cc.content, cc.chapter_id,
               ch.chapter_no, ch.title
        FROM chapter_chunks cc
        JOIN chapters ch ON ch.id = cc.chapter_id
        ORDER BY ch.chapter_no, cc.chunk_no
        """,
    )


def _get_all_worldbuilding(db_path: str) -> list[dict]:
    return _query_rows(
        db_path,
        """
        SELECT id, novel_id, title, content, category, importance
        FROM worldbuilding
        ORDER BY novel_id, importance DESC, id
        """,
    )


def _unavailable_result(error: str) -> dict:
    return {
        "status": "unavailable",
        "error": error,
        "total": 0,
        "indexed": 0,
        "skipped": 0,
    }


def _reset_collection(retriever: VectorRetriever, collection_name: str) -> None:
    try:
        retriever._client.delete_collection(collection_name)
    except Exception:
        pass
    retriever._collection = retriever._client.get_or_create_collection(name=collection_name)


def _existing_ids(retriever: VectorRetriever) -> set[str]:
    try:
        return set(retriever._collection.get()["ids"])
    except Exception:
        return set()


def _index_rows(
    retriever: VectorRetriever,
    rows: list[dict],
    build_record,
    collection_name: str,
    rebuild: bool = False,
) -> dict:
    if not rows:
        return {
            "status": "ok",
            "total": 0,
            "indexed": 0,
            "skipped": 0,
            "message": "没有找到可索引的数据",
        }

    if rebuild:
        try:
            _reset_collection(retriever, collection_name)
        except Exception as exc:
            return {
                "status": "error",
                "error": f"重建集合失败: {exc}",
                "total": len(rows),
                "indexed": 0,
                "skipped": 0,
            }

    existing_ids = set() if rebuild else _existing_ids(retriever)
    batch_size = 64
    indexed = 0
    skipped = 0
    errors: list[str] = []

    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        for row in batch:
            record = build_record(row)
            doc_id = record["id"]
            if doc_id in existing_ids:
                skipped += 1
                continue

            ids.append(doc_id)
            documents.append(record["document"])
            metadatas.append(record["metadata"])

        if not ids:
            continue

        try:
            embeddings = retriever._model.encode(documents).tolist()
            retriever._collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            indexed += len(ids)
        except Exception as exc:
            errors.append(f"批次 {start // batch_size}: {exc}")

    result = {
        "status": "ok" if not errors else "partial",
        "total": len(rows),
        "indexed": indexed,
        "skipped": skipped,
    }
    if errors:
        result["errors"] = errors[:10]
    return result


def index_all(config: dict | None = None, rebuild: bool = False) -> dict:
    """Index all chapter chunks into the default vector collection."""
    config = config or load_rag_config()

    if not HAS_VECTOR_DEPS:
        return _unavailable_result(
            "chromadb / sentence-transformers 未安装，无法建立向量索引",
        )

    db_path = get_db_path(config)
    if not Path(db_path).exists():
        return {
            "status": "error",
            "error": f"数据库不存在: {db_path}",
            "total": 0,
            "indexed": 0,
            "skipped": 0,
        }

    vec_cfg = get_vector_config(config)
    retriever = VectorRetriever(
        persist_dir=vec_cfg["persist_dir"],
        collection_name=vec_cfg["collection_name"],
        embedding_model=vec_cfg["embedding_model"],
    )
    if not retriever.available:
        return _unavailable_result(
            f"VectorRetriever 初始化失败: {getattr(retriever, '_init_error', 'unknown')}",
        )

    def build_record(chunk: dict) -> dict:
        return {
            "id": str(chunk["id"]),
            "document": chunk["content"],
            "metadata": {
                "chapter_id": str(chunk["chapter_id"]),
                "chapter_no": str(chunk["chapter_no"]),
                "chunk_no": str(chunk["chunk_no"]),
                "title": chunk["title"],
            },
        }

    return _index_rows(
        retriever,
        _get_all_chunks(db_path),
        build_record,
        collection_name=vec_cfg["collection_name"],
        rebuild=rebuild,
    )


def index_worldbuilding(config: dict | None = None, rebuild: bool = False) -> dict:
    """Index all worldbuilding rows into the shared worldbuilding collection."""
    config = config or load_rag_config()

    if not HAS_VECTOR_DEPS:
        return _unavailable_result(
            "chromadb / sentence-transformers 未安装，无法建立向量索引",
        )

    db_path = get_db_path(config)
    if not Path(db_path).exists():
        return {
            "status": "error",
            "error": f"数据库不存在: {db_path}",
            "total": 0,
            "indexed": 0,
            "skipped": 0,
        }

    vec_cfg = get_vector_config(config)
    retriever = VectorRetriever(
        persist_dir=vec_cfg["persist_dir"],
        collection_name=WORLD_BUILDING_COLLECTION,
        embedding_model=vec_cfg["embedding_model"],
    )
    if not retriever.available:
        return _unavailable_result(
            f"VectorRetriever 初始化失败: {getattr(retriever, '_init_error', 'unknown')}",
        )

    def build_record(world: dict) -> dict:
        content = world.get("content") or ""
        return {
            "id": str(world["id"]),
            "document": f"{world['title']}\n{content}",
            "metadata": {
                "novel_id": str(world["novel_id"]),
                "title": world["title"],
                "category": world.get("category") or "",
                "importance": int(world.get("importance") or 3),
                "content_preview": content[:300],
            },
        }

    return _index_rows(
        retriever,
        _get_all_worldbuilding(db_path),
        build_record,
        collection_name=WORLD_BUILDING_COLLECTION,
        rebuild=rebuild,
    )


def index_status(config: dict | None = None) -> dict:
    """Return the status of the default chapter-chunk vector collection."""
    config = config or load_rag_config()

    if not HAS_VECTOR_DEPS:
        return {"status": "unavailable", "error": "向量依赖未安装"}

    vec_cfg = get_vector_config(config)
    retriever = VectorRetriever(
        persist_dir=vec_cfg["persist_dir"],
        collection_name=vec_cfg["collection_name"],
        embedding_model=vec_cfg["embedding_model"],
    )
    count = retriever.count()
    return {
        "status": count["status"],
        "vector_count": count.get("count", 0),
    }
