#!/usr/bin/env python3
"""
rag_config.py — RAG 配置加载

从 YAML 配置文件加载 RAG 参数，提供合理默认值。
未提供配置文件时使用内置默认值。
"""

import os
from pathlib import Path
from typing import Optional


# ============================================================
# 默认配置
# ============================================================

DEFAULT_RAG_CONFIG = {
    "db_path": "./data/novel_memory.db",
    "rag": {
        "default_mode": "fts5",
        "top_k": 8,
        "fts5": {
            "enrich_metadata": True,
            "search_chunks": True,
            "chunk_limit": 20,
        },
        "vector": {
            "persist_dir": "./data/rag_vector_store",
            "collection_name": "novel_chunks",
            "embedding_model": "paraphrase-multilingual-MiniLM-L12-v2",
            "top_k": 16,
        },
        "hybrid": {
            "fts5_weight": 0.5,
            "vector_weight": 0.5,
            "top_k": 8,
        },
    },
    "report": {
        "output_dir": "./reports/rag",
        "format": "json",
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并两个字典，override 覆盖 base。"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_rag_config(config_path: Optional[str] = None) -> dict:
    """
    加载 RAG 配置。

    优先级: 传入路径 > 环境变量 RAG_CONFIG_PATH > 默认路径 > 内置默认值

    Args:
        config_path: YAML 配置文件路径 (可选)

    Returns:
        dict: 完整 RAG 配置字典
    """
    # 确定配置文件路径
    resolved_path = config_path
    if not resolved_path:
        resolved_path = os.environ.get("RAG_CONFIG_PATH", "")
    if not resolved_path:
        # 尝试默认路径
        candidates = [
            Path("configs/rag.yaml"),
            Path("configs/rag.yml"),
            Path("rag.yaml"),
            Path("rag.yml"),
        ]
        for candidate in candidates:
            if candidate.exists():
                resolved_path = str(candidate)
                break

    config = DEFAULT_RAG_CONFIG.copy()

    if resolved_path and Path(resolved_path).exists():
        try:
            import yaml

            with open(resolved_path, "r", encoding="utf-8") as f:
                user_config = yaml.safe_load(f)
            if user_config:
                config = _deep_merge(config, user_config)
        except ImportError:
            # 无 pyyaml，尝试 JSON
            import json

            with open(resolved_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            if user_config:
                config = _deep_merge(config, user_config)

    return config


def get_rag_mode(config: dict) -> str:
    """从配置中提取默认检索模式。"""
    return config.get("rag", {}).get("default_mode", "fts5")


def get_db_path(config: dict) -> str:
    """从配置中提取数据库路径。"""
    return config.get("db_path", DEFAULT_RAG_CONFIG["db_path"])
