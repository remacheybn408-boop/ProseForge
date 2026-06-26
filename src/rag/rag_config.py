#!/usr/bin/env python3
"""
rag_config.py — RAG 配置加载

从 YAML 配置文件加载 RAG 参数，提供合理默认值。
未提供配置文件时使用内置默认值。
"""

import os
from pathlib import Path
from typing import Optional

from src.utils.config_utils import DEFAULT_DB_PATH


# ============================================================
# 默认配置
# ============================================================

DEFAULT_VECTOR_PERSIST_DIR = "./data/rag_vector_store"
DEFAULT_VECTOR_COLLECTION_NAME = "novel_chunks"
DEFAULT_VECTOR_EMBEDDING_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"

DEFAULT_RAG_CONFIG = {
    "db_path": DEFAULT_DB_PATH,
    "rag": {
        "default_mode": "fts5",
        "top_k": 8,
        "fts5": {
            "enrich_metadata": True,
            "search_chunks": True,
            "chunk_limit": 20,
        },
        "vector": {
            "persist_dir": DEFAULT_VECTOR_PERSIST_DIR,
            "collection_name": DEFAULT_VECTOR_COLLECTION_NAME,
            "embedding_model": DEFAULT_VECTOR_EMBEDDING_MODEL,
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
    """从配置中提取数据库路径，优先使用活跃 slot 的 novel.db。"""
    # Try to resolve from active slot first
    try:
        import json as _j
        ws = Path("workspace")
        reg_file = ws / "registry.json"
        if reg_file.exists():
            reg = _j.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            if active:
                slot_db = ws / active / "novel.db"
                if slot_db.exists():
                    return str(slot_db)
    except Exception:
        pass
    return config.get("db_path", DEFAULT_RAG_CONFIG["db_path"])


def get_vector_config(config: dict | None = None) -> dict:
    """Return vector config with centralized defaults applied."""
    vec_cfg = (config or {}).get("rag", {}).get("vector", {})
    return {
        "persist_dir": vec_cfg.get("persist_dir", DEFAULT_VECTOR_PERSIST_DIR),
        "collection_name": vec_cfg.get("collection_name", DEFAULT_VECTOR_COLLECTION_NAME),
        "embedding_model": vec_cfg.get("embedding_model", DEFAULT_VECTOR_EMBEDDING_MODEL),
        "top_k": vec_cfg.get("top_k", DEFAULT_RAG_CONFIG["rag"]["vector"]["top_k"]),
    }
