#!/usr/bin/env python3
"""
rag_query.py — RAG 查询入口

提供统一的检索接口，支持三种模式:
  - fts5:   纯 FTS5 全文检索 (默认，无须额外依赖)
  - vector: 向量语义检索 (需要 chromadb + sentence-transformers)
  - hybrid: 混合检索 FTS5+Vector (需要向量依赖)

用法:
  from scripts.rag.rag_query import rag_query

  result = rag_query("主角的能力是什么？", db_path="./data/novel_memory.db", mode="fts5")
  print(result["answer"])
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from .rag_config import load_rag_config, get_db_path, get_rag_mode
from .fts5_retriever import search_chapters, search_chunks
from .hybrid_retriever import hybrid_search
from .vector_retriever import search as vector_search


def _save_report(report: dict, output_dir: str = "./reports/rag") -> Optional[str]:
    """
    将查询报告保存为 JSON 文件到 reports/rag/ 目录。

    Returns:
        str: 保存的文件路径，失败返回 None
    """
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"rag_query_{ts}.json"
        filepath = output_path / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        return str(filepath)
    except Exception:
        return None


def rag_query(
    question: str,
    db_path: str = None,
    mode: str = None,
    config_path: str = None,
    top_k: int = None,
) -> dict:
    """
    RAG 查询主函数。

    Args:
        question: 查询问题
        db_path: SQLite 数据库路径 (可选，优先于配置文件)
        mode: 检索模式 "fts5" / "vector" / "hybrid" (可选，优先于配置文件)
        config_path: RAG YAML 配置文件路径 (可选)
        top_k: 返回结果数 (可选，优先于配置文件)

    Returns:
        dict: {
            "query": str,            # 原始查询
            "mode": str,             # 实际使用的模式 (可能因降级而改变)
            "results": list[dict],   # 检索结果 [{chapter_no, title, evidence, score, source}, ...]
            "answer": str,           # 拼接的上下文片段 (供 LLM 使用)
            "degraded": bool,        # 是否因依赖缺失而降级
            "degraded_reason": str,  # 降级原因
            "report_path": str,      # JSON 报告保存路径
        }
    """
    # ---- 加载配置 ----
    config = load_rag_config(config_path)
    if db_path is None:
        db_path = get_db_path(config)
    if mode is None:
        mode = get_rag_mode(config)
    if top_k is None:
        top_k = config.get("rag", {}).get("top_k", 8)

    degraded = False
    degraded_reason = ""

    # ---- 实际模式决策 (考虑降级) ----
    actual_mode = mode
    if mode in ("vector", "hybrid"):
        from .vector_retriever import HAS_VECTOR_DEPS
        if not HAS_VECTOR_DEPS:
            actual_mode = "fts5"
            degraded = True
            degraded_reason = f"向量依赖未安装，'{mode}' 降级为 'fts5'。请执行: pip install -r requirements-rag.txt"

    # ---- 执行检索 ----
    results = []
    search_meta = {}

    if actual_mode == "fts5":
        # 同时检索章节和分块，合并去重
        ch_result = search_chapters(question, db_path, top_k=top_k)
        ck_result = search_chunks(question, db_path, top_k=top_k * 2)

        seen_ids = set()
        merged = []

        if ch_result["status"] == "ok":
            for item in ch_result["results"]:
                key = f"ch_{item.get('chapter_id', '')}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    merged.append(item)

        if ck_result["status"] == "ok":
            for item in ck_result["results"]:
                # 对于 chunk 结果，按 chapter_id 去重
                key = f"ch_{item.get('chapter_id', '')}"
                if key not in seen_ids:
                    seen_ids.add(key)
                    merged.append(item)

        results = merged[:top_k]
        search_meta = {
            "fts5_chapter_method": ch_result.get("method", "fts5"),
            "fts5_chunk_method": ck_result.get("method", "fts5"),
        }

    elif actual_mode == "vector":
        vec_cfg = config.get("rag", {}).get("vector", {})
        vec_result = vector_search(question, top_k=top_k, config=config)
        if vec_result["status"] == "ok":
            results = vec_result["results"]
        else:
            # 向量不可用，降级到 FTS5
            actual_mode = "fts5"
            degraded = True
            degraded_reason = f"向量检索失败: {vec_result.get('error', 'unknown')}，降级为 fts5"
            ch_result = search_chapters(question, db_path, top_k=top_k)
            if ch_result["status"] == "ok":
                results = ch_result["results"]
        search_meta["vector_status"] = vec_result.get("status", "unknown")

    elif actual_mode == "hybrid":
        vec_cfg = config.get("rag", {}).get("vector", {})
        hy_cfg = config.get("rag", {}).get("hybrid", {})
        hy_result = hybrid_search(
            query=question,
            db_path=db_path,
            vector_config=vec_cfg,
            fts5_weight=hy_cfg.get("fts5_weight", 0.5),
            vector_weight=hy_cfg.get("vector_weight", 0.5),
            top_k=top_k,
        )
        results = hy_result.get("results", [])
        if hy_result.get("mode") in ("fts5_fallback", "vector_fallback"):
            degraded = True
            degraded_reason = hy_result.get("degraded_reason", "混合检索部分降级")
        search_meta = {
            "hybrid_mode": hy_result.get("mode", "hybrid"),
            "fts5_count": hy_result.get("fts5_count", 0),
            "vector_count": hy_result.get("vector_count", 0),
        }

    # ---- 构建上下文 (answer) ----
    evidence_parts = []
    for i, item in enumerate(results):
        ch_no = item.get("chapter_no", "?")
        title = item.get("title", "")
        evidence = item.get("evidence", "")
        source = item.get("source", actual_mode)
        score = item.get("score", 0)
        part = f"[第{ch_no}章 {title}] (score={score}, src={source})\n{evidence}"
        evidence_parts.append(part)

    answer = "\n\n---\n\n".join(evidence_parts) if evidence_parts else "(未找到相关内容)"

    # ---- 构建报告 ----
    report = {
        "timestamp": datetime.now().isoformat(),
        "query": question,
        "mode": actual_mode,
        "requested_mode": mode,
        "db_path": db_path,
        "top_k": top_k,
        "degraded": degraded,
        "degraded_reason": degraded_reason if degraded else "",
        "result_count": len(results),
        "results": results,
        "search_meta": search_meta,
        "answer": answer,
    }

    # ---- 保存报告 ----
    output_dir = config.get("report", {}).get("output_dir", "./reports/rag")
    report_path = _save_report(report, output_dir)
    if report_path:
        report["report_path"] = report_path

    return report


# ============================================================
# CLI
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="RAG 查询工具")
    parser.add_argument("query", nargs="?", default=None, help="查询文本")
    parser.add_argument("--db-path", default=None, help="SQLite 数据库路径")
    parser.add_argument("--mode", choices=["fts5", "vector", "hybrid"], default=None,
                        help="检索模式 (默认: 配置文件中的 default_mode)")
    parser.add_argument("--config", default=None, help="RAG YAML 配置文件路径")
    parser.add_argument("--top-k", type=int, default=None, help="返回结果数")
    parser.add_argument("--no-save", action="store_true", help="不保存报告到文件")
    args = parser.parse_args()

    if not args.query:
        # 交互模式
        print("RAG 查询工具 (输入 'quit' 退出)")
        db_path = args.db_path
        mode = args.mode
        while True:
            try:
                q = input("\n查询> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not q:
                continue
            if q.lower() in ("quit", "exit", "q"):
                break
            result = rag_query(
                question=q,
                db_path=db_path,
                mode=mode,
                config_path=args.config,
                top_k=args.top_k,
            )
            print(f"\n模式: {result['mode']}")
            if result["degraded"]:
                print(f"注意: {result['degraded_reason']}")
            print(f"结果数: {result['result_count']}")
            print(f"\n{result['answer']}")
            if result.get("report_path"):
                print(f"\n报告已保存: {result['report_path']}")
    else:
        # 单次查询
        result = rag_query(
            question=args.query,
            db_path=args.db_path,
            mode=args.mode,
            config_path=args.config,
            top_k=args.top_k,
        )
        if args.no_save:
            result.pop("report_path", None)
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
