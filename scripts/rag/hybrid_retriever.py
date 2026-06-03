#!/usr/bin/env python3
"""
hybrid_retriever.py — 混合检索器 (FTS5 + Vector 合并排序)

使用 Reciprocal Rank Fusion (RRF) 融合 FTS5 和向量检索结果：
  score(doc) = sum( weight_i / (k + rank_i) )

FTS5 不可用时仅使用向量结果；向量不可用时降级为纯 FTS5。
"""

from typing import Optional

# 同包导入
from .fts5_retriever import search_chapters as fts5_search_chapters
from .fts5_retriever import search_chunks as fts5_search_chunks
from .vector_retriever import VectorRetriever, HAS_VECTOR_DEPS


def _rrf_fusion(
    fts5_results: list[dict],
    vector_results: list[dict],
    fts5_weight: float = 0.5,
    vector_weight: float = 0.5,
    k: int = 60,
    dedup_key: str = "chapter_id",
    top_k: int = 8,
) -> list[dict]:
    """
    使用 Reciprocal Rank Fusion 合并两组结果。

    Args:
        fts5_results: FTS5 检索结果
        vector_results: 向量检索结果
        fts5_weight: FTS5 权重
        vector_weight: 向量权重
        k: RRF 平滑参数 (默认 60)
        dedup_key: 去重键 (chapter_id 或 chunk_id)
        top_k: 最终返回数

    Returns:
        list[dict]: 合并排序后的结果
    """
    scores = {}  # {dedup_key: {"score": float, "item": dict, "sources": [str]}}

    # 处理 FTS5 结果
    for rank, item in enumerate(fts5_results):  # rank 从 0 开始
        key = item.get(dedup_key, f"fts5_{rank}")
        rrf_score = fts5_weight / (k + rank + 1)
        if key not in scores:
            scores[key] = {"score": 0.0, "item": item, "sources": []}
        scores[key]["score"] += rrf_score
        scores[key]["sources"].append(item.get("source", "fts5"))

    # 处理 Vector 结果
    if vector_results:
        for rank, item in enumerate(vector_results):
            # 尝试匹配到已有的章节
            key = item.get(dedup_key, f"vec_{rank}")
            rrf_score = vector_weight / (k + rank + 1)
            if key not in scores:
                scores[key] = {"score": 0.0, "item": item, "sources": []}
            scores[key]["score"] += rrf_score
            scores[key]["sources"].append(item.get("source", "vector"))

    # 排序与截断
    sorted_items = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
    top_results = []
    for key, data in sorted_items[:top_k]:
        item = data["item"].copy()
        item["score"] = round(data["score"], 6)
        item["source"] = "hybrid(" + "+".join(sorted(set(data["sources"]))) + ")"
        top_results.append(item)

    return top_results


def hybrid_search(
    query: str,
    db_path: str,
    vector_config: Optional[dict] = None,
    fts5_weight: float = 0.5,
    vector_weight: float = 0.5,
    top_k: int = 8,
    fts5_top_k: int = 10,
    vector_top_k: int = 16,
) -> dict:
    """
    混合检索: FTS5 + Vector 融合。

    Args:
        query: 查询文本
        db_path: SQLite 数据库路径
        vector_config: RAG 配置中 vector 部分的字典
        fts5_weight: FTS5 权重
        vector_weight: 向量权重
        top_k: 最终返回结果数
        fts5_top_k: FTS5 检索数量
        vector_top_k: 向量检索数量

    Returns:
        dict: {
            "status": "ok" | "degraded" | "error",
            "mode": "hybrid" | "fts5_fallback" | "vector_fallback",
            "results": [...],
            "fts5_count": int,
            "vector_count": int,
        }
    """
    fts5_results = []
    vector_results = []
    fts5_status = "ok"
    vector_status = "unavailable"

    # ---- FTS5 检索 ----
    try:
        fts5_result = fts5_search_chunks(
            query=query,
            db_path=db_path,
            top_k=fts5_top_k,
            enrich=True,
        )
        if fts5_result["status"] == "ok":
            fts5_results = fts5_result["results"]
        else:
            fts5_status = fts5_result["status"]
    except Exception as e:
        fts5_status = f"error: {e}"

    # ---- Vector 检索 ----
    if HAS_VECTOR_DEPS:
        try:
            persist_dir = "./data/rag_vector_store"
            collection_name = "novel_chunks"
            embedding_model = "paraphrase-multilingual-MiniLM-L12-v2"
            if vector_config:
                persist_dir = vector_config.get("persist_dir", persist_dir)
                collection_name = vector_config.get("collection_name", collection_name)
                embedding_model = vector_config.get("embedding_model", embedding_model)

            retriever = VectorRetriever(
                persist_dir=persist_dir,
                collection_name=collection_name,
                embedding_model=embedding_model,
            )
            if retriever.available:
                vec_result = retriever.search(query, top_k=vector_top_k)
                if vec_result["status"] == "ok":
                    vector_results = vec_result["results"]
                    vector_status = "ok"
                else:
                    vector_status = vec_result["status"]
            else:
                vector_status = "unavailable"
        except Exception as e:
            vector_status = f"error: {e}"

    # ---- 决策 ----
    # 场景1: FTS5 可用 + Vector 可用 → 真正混合
    if fts5_results and vector_results:
        merged = _rrf_fusion(
            fts5_results=fts5_results,
            vector_results=vector_results,
            fts5_weight=fts5_weight,
            vector_weight=vector_weight,
            top_k=top_k,
        )
        return {
            "status": "ok",
            "mode": "hybrid",
            "results": merged,
            "fts5_count": len(fts5_results),
            "vector_count": len(vector_results),
        }

    # 场景2: 仅 FTS5 可用
    if fts5_results:
        return {
            "status": "degraded",
            "mode": "fts5_fallback",
            "results": fts5_results[:top_k],
            "fts5_count": len(fts5_results),
            "vector_count": len(vector_results),
            "degraded_reason": "vector search unavailable or returned no results",
        }

    # 场景3: 仅 Vector 可用
    if vector_results:
        return {
            "status": "degraded",
            "mode": "vector_fallback",
            "results": vector_results[:top_k],
            "fts5_count": len(fts5_results),
            "vector_count": len(vector_results),
            "degraded_reason": f"FTS5 search failed: {fts5_status}",
        }

    # 场景4: 全部失败
    return {
        "status": "error",
        "mode": "hybrid",
        "results": [],
        "fts5_count": 0,
        "vector_count": 0,
        "error": f"Both FTS5 and vector search failed. FTS5: {fts5_status}, Vector: {vector_status}",
    }
