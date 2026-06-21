#!/usr/bin/env python3
"""Public exports for the RAG package."""

from .fts5_retriever import search_chapters, search_chunks
from .hybrid_retriever import hybrid_search
from .rag_config import get_db_path, get_rag_mode, load_rag_config
from .rag_indexer import index_all, index_status, index_worldbuilding
from .rag_query import rag_query
from .vector_retriever import (
    HAS_VECTOR_DEPS,
    VectorRetriever,
    search as vector_search,
    search_worldbuilding,
)

__all__ = [
    "load_rag_config",
    "get_rag_mode",
    "get_db_path",
    "search_chapters",
    "search_chunks",
    "VectorRetriever",
    "vector_search",
    "search_worldbuilding",
    "hybrid_search",
    "index_all",
    "index_worldbuilding",
    "index_status",
    "rag_query",
    "HAS_VECTOR_DEPS",
]
