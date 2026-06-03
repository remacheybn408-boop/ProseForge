#!/usr/bin/env python3
"""
vector_retriever.py — 向量检索器 (chromadb)

依赖:
  - chromadb>=0.4.0  (pip install chromadb)
  - sentence-transformers>=2.2.0  (pip install sentence-transformers)

未安装依赖时优雅降级，返回 unavailable 状态。
"""

import os
from pathlib import Path
from typing import Optional

# ============================================================
# 优雅降级: 检测向量依赖是否可用
# ============================================================

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    HAS_CHROMA = True
except ImportError:
    HAS_CHROMA = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

HAS_VECTOR_DEPS = HAS_CHROMA and HAS_SENTENCE_TRANSFORMERS


# ============================================================
# VectorRetriever 类
# ============================================================

class VectorRetriever:
    """
    向量检索器。

    使用 chromadb 存储文档向量，sentence-transformers 生成 embedding。
    未安装依赖时所有方法返回降级结果。
    """

    def __init__(
        self,
        persist_dir: str = "./data/rag_vector_store",
        collection_name: str = "novel_chunks",
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
    ):
        """
        Args:
            persist_dir: chromadb 持久化目录
            collection_name: 集合名称
            embedding_model: sentence-transformers 模型名
        """
        self.persist_dir = persist_dir
        self.collection_name = collection_name
        self.embedding_model = embedding_model
        self._client = None
        self._collection = None
        self._model = None
        self._initialized = False

        if HAS_VECTOR_DEPS:
            self._init()
        else:
            missing = []
            if not HAS_CHROMA:
                missing.append("chromadb")
            if not HAS_SENTENCE_TRANSFORMERS:
                missing.append("sentence-transformers")
            self._init_error = f"缺少依赖: {', '.join(missing)}"

    def _init(self):
        """初始化 chromadb 客户端和 embedding 模型。"""
        try:
            Path(self.persist_dir).mkdir(parents=True, exist_ok=True)

            self._client = chromadb.PersistentClient(
                path=self.persist_dir,
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
            )
            self._model = SentenceTransformer(self.embedding_model)
            self._initialized = True
        except Exception as e:
            self._init_error = str(e)
            self._initialized = False

    @property
    def available(self) -> bool:
        """向量检索是否可用。"""
        return self._initialized

    def search(
        self,
        query: str,
        top_k: int = 16,
    ) -> dict:
        """
        向量相似度检索。

        Args:
            query: 查询文本
            top_k: 返回结果数

        Returns:
            dict: {
                "status": "ok" | "unavailable" | "error",
                "results": [{chunk_id, chapter_no, title, evidence, score, source}, ...],
                ...
            }
        """
        if not HAS_VECTOR_DEPS:
            missing = []
            if not HAS_CHROMA:
                missing.append("chromadb")
            if not HAS_SENTENCE_TRANSFORMERS:
                missing.append("sentence-transformers")
            return {
                "status": "unavailable",
                "results": [],
                "error": f"向量依赖未安装: {', '.join(missing)}。请执行: pip install -r requirements-rag.txt",
            }

        if not self._initialized:
            return {
                "status": "unavailable",
                "results": [],
                "error": f"VectorRetriever 初始化失败: {getattr(self, '_init_error', 'unknown')}",
            }

        try:
            # 生成查询向量
            query_embedding = self._model.encode([query])[0].tolist()

            # chromadb 查询
            chroma_results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )

            # 格式化结果
            results = []
            if chroma_results and chroma_results.get("ids"):
                ids = chroma_results["ids"][0]  # 第一个查询的结果
                distances = chroma_results.get("distances", [[0] * len(ids)])[0]
                metadatas = chroma_results.get("metadatas", [[{}] * len(ids)])[0]
                documents = chroma_results.get("documents", [[""] * len(ids)])[0]

                for i, doc_id in enumerate(ids):
                    meta = metadatas[i] if i < len(metadatas) else {}
                    doc = documents[i] if i < len(documents) else ""
                    # chromadb 返回的是 distance，转换为 similarity score
                    distance = distances[i] if i < len(distances) else 0
                    # cosine distance -> cosine similarity: 1 - distance for normalized
                    score = max(0.0, 1.0 - min(1.0, distance)) if distance else 1.0

                    results.append({
                        "chunk_id": doc_id,
                        "chapter_no": meta.get("chapter_no", ""),
                        "chapter_id": meta.get("chapter_id", ""),
                        "title": meta.get("title", ""),
                        "evidence": doc[:300] if doc else "",
                        "score": round(score, 4),
                        "source": "vector",
                    })

            return {
                "status": "ok",
                "results": results,
            }

        except Exception as e:
            return {
                "status": "error",
                "results": [],
                "error": str(e),
            }

    def count(self) -> dict:
        """返回集合中的文档数量。"""
        if not self._initialized:
            return {"status": "unavailable", "count": 0}
        try:
            return {"status": "ok", "count": self._collection.count()}
        except Exception as e:
            return {"status": "error", "count": 0, "error": str(e)}


# ============================================================
# 便捷函数
# ============================================================

def search(query: str, top_k: int = 8, config: Optional[dict] = None) -> dict:
    """
    向量检索快捷入口。

    Args:
        query: 查询文本
        top_k: 返回结果数
        config: RAG 配置字典 (可选，用于读取 persist_dir 等参数)

    Returns:
        dict: 同 VectorRetriever.search()
    """
    if not HAS_VECTOR_DEPS:
        return {
            "status": "unavailable",
            "results": [],
            "error": "chromadb / sentence-transformers not installed",
        }

    persist_dir = "./data/rag_vector_store"
    collection_name = "novel_chunks"
    embedding_model = "paraphrase-multilingual-MiniLM-L12-v2"

    if config:
        vec_cfg = config.get("rag", {}).get("vector", {})
        persist_dir = vec_cfg.get("persist_dir", persist_dir)
        collection_name = vec_cfg.get("collection_name", collection_name)
        embedding_model = vec_cfg.get("embedding_model", embedding_model)
        top_k = vec_cfg.get("top_k", top_k)

    retriever = VectorRetriever(
        persist_dir=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model,
    )
    return retriever.search(query, top_k=top_k)
