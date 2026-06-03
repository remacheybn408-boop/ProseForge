#!/usr/bin/env python3
"""
rag_indexer.py — RAG 索引导入器

将数据库中已有的章节分块导入向量存储 (chromadb)。
支持增量索引 (跳过已存在文档) 和全量重建。

用法:
  python -m scripts.rag.rag_indexer --db-path ./data/novel_memory.db --rebuild
"""

import sqlite3
import sys
from pathlib import Path

from .rag_config import load_rag_config, get_db_path
from .vector_retriever import VectorRetriever, HAS_VECTOR_DEPS


def _get_all_chunks(db_path: str) -> list[dict]:
    """
    从数据库读取所有分块及所属章节元数据。

    Returns:
        list[dict]: [{id, chunk_no, content, chapter_id, chapter_no, title}]
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("""
        SELECT cc.id, cc.chunk_no, cc.content, cc.chapter_id,
               ch.chapter_no, ch.title
        FROM chapter_chunks cc
        JOIN chapters ch ON ch.id = cc.chapter_id
        ORDER BY ch.chapter_no, cc.chunk_no
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


def index_all(config: dict = None, rebuild: bool = False) -> dict:
    """
    将所有章节分块导入向量存储。

    Args:
        config: RAG 配置字典 (可选)
        rebuild: 是否清空重建 (默认增量)

    Returns:
        dict: {"status": "ok"|"error"|"unavailable",
               "total": int, "indexed": int, "skipped": int, ...}
    """
    if not config:
        config = load_rag_config()

    if not HAS_VECTOR_DEPS:
        return {
            "status": "unavailable",
            "error": "chromadb / sentence-transformers 未安装，无法建立向量索引",
            "total": 0,
            "indexed": 0,
            "skipped": 0,
        }

    db_path = get_db_path(config)
    vec_cfg = config.get("rag", {}).get("vector", {})

    persist_dir = vec_cfg.get("persist_dir", "./data/rag_vector_store")
    collection_name = vec_cfg.get("collection_name", "novel_chunks")
    embedding_model = vec_cfg.get("embedding_model", "paraphrase-multilingual-MiniLM-L12-v2")

    # 检查数据库
    if not Path(db_path).exists():
        return {
            "status": "error",
            "error": f"数据库不存在: {db_path}",
            "total": 0,
            "indexed": 0,
            "skipped": 0,
        }

    # 初始化向量检索器
    retriever = VectorRetriever(
        persist_dir=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model,
    )

    if not retriever.available:
        return {
            "status": "unavailable",
            "error": f"VectorRetriever 初始化失败: {getattr(retriever, '_init_error', 'unknown')}",
            "total": 0,
            "indexed": 0,
            "skipped": 0,
        }

    # 读取分块
    chunks = _get_all_chunks(db_path)
    if not chunks:
        return {
            "status": "ok",
            "total": 0,
            "indexed": 0,
            "skipped": 0,
            "message": "没有找到任何章节分块",
        }

    # 如果重建，删除集合并重建
    if rebuild:
        try:
            retriever._client.delete_collection(collection_name)
            retriever._collection = retriever._client.get_or_create_collection(
                name=collection_name,
            )
        except Exception as e:
            return {
                "status": "error",
                "error": f"重建集合失败: {e}",
                "total": len(chunks),
                "indexed": 0,
                "skipped": 0,
            }

    # 获取已存在的 ID 集合 (增量检查)
    existing_ids = set()
    if not rebuild:
        try:
            all_ids = retriever._collection.get()["ids"]
            existing_ids = set(all_ids)
        except Exception:
            pass  # 集合为空

    # 分批处理 (每批 64 条，避免 OOM)
    batch_size = 64
    total = len(chunks)
    indexed = 0
    skipped = 0
    errors = []

    for i in range(0, total, batch_size):
        batch = chunks[i : i + batch_size]
        ids = []
        documents = []
        metadatas = []

        for chunk in batch:
            doc_id = str(chunk["id"])
            if doc_id in existing_ids:
                skipped += 1
                continue

            ids.append(doc_id)
            documents.append(chunk["content"])
            metadatas.append({
                "chapter_id": str(chunk["chapter_id"]),
                "chapter_no": str(chunk["chapter_no"]),
                "chunk_no": str(chunk["chunk_no"]),
                "title": chunk["title"],
            })

        if not ids:
            continue  # 整批都跳过

        try:
            # 生成 embedding 并写入
            embeddings = retriever._model.encode(documents).tolist()
            retriever._collection.add(
                ids=ids,
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
            )
            indexed += len(ids)
        except Exception as e:
            errors.append(f"批次 {i//batch_size}: {e}")

    result = {
        "status": "ok" if not errors else "partial",
        "total": total,
        "indexed": indexed,
        "skipped": skipped,
    }
    if errors:
        result["errors"] = errors[:10]  # 最多保留10条错误

    return result


def index_status(config: dict = None) -> dict:
    """查询向量索引状态。"""
    if not config:
        config = load_rag_config()

    if not HAS_VECTOR_DEPS:
        return {"status": "unavailable", "error": "向量依赖未安装"}

    vec_cfg = config.get("rag", {}).get("vector", {})
    retriever = VectorRetriever(
        persist_dir=vec_cfg.get("persist_dir", "./data/rag_vector_store"),
        collection_name=vec_cfg.get("collection_name", "novel_chunks"),
    )
    count = retriever.count()
    return {
        "status": count["status"],
        "vector_count": count.get("count", 0),
    }


# ============================================================
# CLI
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAG 向量索引导入")
    parser.add_argument("--db-path", default=None, help="SQLite 数据库路径")
    parser.add_argument("--config", default=None, help="RAG YAML 配置文件")
    parser.add_argument("--rebuild", action="store_true", help="清空并重建索引")
    parser.add_argument("--status", action="store_true", help="仅查看索引状态")
    args = parser.parse_args()

    import json

    if args.status:
        config = load_rag_config(args.config)
        result = index_status(config)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    config = load_rag_config(args.config)
    if args.db_path:
        config["db_path"] = args.db_path

    print(f"数据库: {config.get('db_path')}")
    print(f"模式: {'全量重建' if args.rebuild else '增量索引'}")
    print("索引中...")

    result = index_all(config, rebuild=args.rebuild)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
