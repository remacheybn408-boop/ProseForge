#!/usr/bin/env python3
"""Vector retrieval helpers backed by ChromaDB."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .rag_config import get_vector_config

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


def _missing_deps_error() -> str:
    missing = []
    if not HAS_CHROMA:
        missing.append("chromadb")
    if not HAS_SENTENCE_TRANSFORMERS:
        missing.append("sentence-transformers")
    return ", ".join(missing)


def _distance_to_score(distance) -> float:
    if distance is None:
        return 1.0
    distance = float(distance)
    return max(0.0, 1.0 - min(1.0, distance))


def _get_vector_settings(config: Optional[dict] = None) -> tuple[str, str, str]:
    vec_cfg = get_vector_config(config)
    return (
        vec_cfg["persist_dir"],
        vec_cfg["collection_name"],
        vec_cfg["embedding_model"],
    )


class VectorRetriever:
    """Thin ChromaDB + SentenceTransformer wrapper."""

    def __init__(
        self,
        persist_dir: str | None = None,
        collection_name: str | None = None,
        embedding_model: str | None = None,
    ):
        defaults = get_vector_config()
        self.persist_dir = persist_dir or defaults["persist_dir"]
        self.collection_name = collection_name or defaults["collection_name"]
        self.embedding_model = embedding_model or defaults["embedding_model"]
        self._client = None
        self._collection = None
        self._model = None
        self._initialized = False

        if HAS_VECTOR_DEPS:
            self._init()
        else:
            self._init_error = f"缺少依赖: {_missing_deps_error()}"

    def _init(self):
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
        except Exception as exc:
            self._init_error = str(exc)
            self._initialized = False

    @property
    def available(self) -> bool:
        return self._initialized

    def search(
        self,
        query: str,
        top_k: int = 16,
    ) -> dict:
        if not HAS_VECTOR_DEPS:
            return {
                "status": "unavailable",
                "results": [],
                "error": (
                    f"向量依赖未安装: {_missing_deps_error()}。"
                    "请执行: pip install -r requirements-rag.txt"
                ),
            }

        if not self._initialized:
            return {
                "status": "unavailable",
                "results": [],
                "error": f"VectorRetriever 初始化失败: {getattr(self, '_init_error', 'unknown')}",
            }

        try:
            query_embedding = self._model.encode([query])[0].tolist()
            chroma_results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
            )

            results = []
            if chroma_results and chroma_results.get("ids"):
                ids = chroma_results["ids"][0]
                distances = chroma_results.get("distances", [[0] * len(ids)])[0]
                metadatas = chroma_results.get("metadatas", [[{}] * len(ids)])[0]
                documents = chroma_results.get("documents", [[""] * len(ids)])[0]

                for i, doc_id in enumerate(ids):
                    meta = metadatas[i] if i < len(metadatas) else {}
                    doc = documents[i] if i < len(documents) else ""
                    distance = distances[i] if i < len(distances) else 0
                    results.append(
                        {
                            "chunk_id": doc_id,
                            "chapter_no": meta.get("chapter_no", ""),
                            "chapter_id": meta.get("chapter_id", ""),
                            "title": meta.get("title", ""),
                            "evidence": doc[:300] if doc else "",
                            "score": round(_distance_to_score(distance), 4),
                            "source": "vector",
                        }
                    )

            return {
                "status": "ok",
                "results": results,
            }
        except Exception as exc:
            return {
                "status": "error",
                "results": [],
                "error": str(exc),
            }

    def count(self) -> dict:
        if not self._initialized:
            return {"status": "unavailable", "count": 0}
        try:
            return {"status": "ok", "count": self._collection.count()}
        except Exception as exc:
            return {"status": "error", "count": 0, "error": str(exc)}


def search(query: str, top_k: int = 8, config: Optional[dict] = None) -> dict:
    """Convenience entry point for chapter-chunk vector search."""
    if not HAS_VECTOR_DEPS:
        return {
            "status": "unavailable",
            "results": [],
            "error": "chromadb / sentence-transformers not installed",
        }

    persist_dir, collection_name, embedding_model = _get_vector_settings(config)
    if config:
        top_k = config.get("rag", {}).get("vector", {}).get("top_k", top_k)

    retriever = VectorRetriever(
        persist_dir=persist_dir,
        collection_name=collection_name,
        embedding_model=embedding_model,
    )
    return retriever.search(query, top_k=top_k)


def search_worldbuilding(
    query: str,
    novel_id: int,
    top_k: int = 8,
    config: Optional[dict] = None,
) -> dict:
    """Semantic search over the shared worldbuilding vector collection."""
    if not HAS_VECTOR_DEPS:
        return {
            "status": "unavailable",
            "results": [],
            "error": "chromadb / sentence-transformers not installed",
        }

    persist_dir, _, embedding_model = _get_vector_settings(config)
    retriever = VectorRetriever(
        persist_dir=persist_dir,
        collection_name="novel_worldbuilding",
        embedding_model=embedding_model,
    )

    if not retriever.available:
        return {
            "status": "unavailable",
            "results": [],
            "error": f"VectorRetriever 初始化失败: {getattr(retriever, '_init_error', 'unknown')}",
        }

    try:
        query_embedding = retriever._model.encode([query])[0].tolist()
        chroma_results = retriever._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where={"novel_id": str(novel_id)},
        )

        results = []
        if chroma_results and chroma_results.get("ids"):
            ids = chroma_results["ids"][0]
            distances = chroma_results.get("distances", [[0] * len(ids)])[0]
            metadatas = chroma_results.get("metadatas", [[{}] * len(ids)])[0]

            for i, doc_id in enumerate(ids):
                meta = metadatas[i] if i < len(metadatas) else {}
                distance = distances[i] if i < len(distances) else 0
                results.append(
                    {
                        "id": doc_id,
                        "title": meta.get("title", ""),
                        "category": meta.get("category", ""),
                        "importance": meta.get("importance", 3),
                        "content_preview": meta.get("content_preview", ""),
                        "score": round(_distance_to_score(distance), 4),
                    }
                )

        return {
            "status": "ok",
            "results": results,
        }
    except Exception as exc:
        return {
            "status": "error",
            "results": [],
            "error": str(exc),
        }
