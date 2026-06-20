#!/usr/bin/env python3
"""
scripts/rag/ — RAG 检索增强系统

提供基于 SQLite FTS5 + chromadb 向量检索的混合知识检索能力。

模块:
  - rag_config:    配置加载
  - fts5_retriever: FTS5 全文检索 (默认可用)
  - vector_retriever: 向量语义检索 (需额外依赖)
  - hybrid_retriever: FTS5 + Vector 混合检索
  - rag_indexer:    向量索引导入
  - rag_query:      统一查询入口

关键设计:
  - 默认使用 SQLite FTS5，零额外依赖
  - 向量/混合模式在未安装 chromadb 时自动降级
  - 所有函数返回结构化 dict，不会因缺依赖而崩溃
  - 查询结果带出处 (chapter_no, title, evidence, score, source)
"""

from .rag_config import load_rag_config, get_rag_mode, get_db_path
from .fts5_retriever import search_chapters, search_chunks
from .vector_retriever import VectorRetriever, search as vector_search, HAS_VECTOR_DEPS
from .hybrid_retriever import hybrid_search
from .rag_indexer import index_all, index_status
from .rag_query import rag_query

__all__ = [
    # 配置
    "load_rag_config",
    "get_rag_mode",
    "get_db_path",
    # 检索器
    "search_chapters",
    "search_chunks",
    "VectorRetriever",
    "vector_search",
    "hybrid_search",
    # 索引
    "index_all",
    "index_status",
    # 主入口
    "rag_query",
    # 能力检测
    "HAS_VECTOR_DEPS",
]
