#!/usr/bin/env python3
"""
check_schema.py — 数据库 Schema 检查

用法:
  python scripts/check_schema.py --config config.json
  python scripts/check_schema.py --db-path ./data/novel_memory.db

功能:
  1. 检查数据库是否存在
  2. 检查必要表是否存在
  3. 检查关键字段是否存在
  4. 输出缺失项（不自动修改数据库）
"""

import sqlite3, sys, argparse, json
from pathlib import Path


# 必需的表及其关键字段
REQUIRED_TABLES = {
    "novels": ["id", "slug", "title", "status"],
    "chapters": ["id", "novel_id", "chapter_no", "title", "content", "word_count", "status"],
    "chapter_versions": ["id", "novel_id", "chapter_no", "version_no", "content", "word_count"],
    "chapter_summaries": ["id", "novel_id", "chapter_id", "short_summary", "long_summary"],
    "chapter_chunks": ["id", "novel_id", "chapter_id", "chunk_no", "content"],
    "characters": ["id", "novel_id", "name", "role", "identity"],
    "worldbuilding": ["id", "novel_id", "title", "category", "importance"],
    "plot_threads": ["id", "novel_id", "title", "status"],
    "writing_rules": ["id", "novel_id", "title", "rule_type"],
    "continuity_checks": ["id", "novel_id", "chapter_id", "check_type"],
    "novel_logs": ["id", "action"],
    "reader_promises": ["id", "novel_id", "promise_title", "status"],
    "volume_plans": ["id", "novel_id", "volume_no", "planned_title", "volume_goal"],
    "chapter_plans": ["id", "novel_id", "volume_no", "chapter_no", "chapter_goal", "conflict_point", "ending_hook_direction", "plan_status", "actual_word_count", "completion_status"],
    "title_history": ["id", "novel_id", "old_title", "new_title", "change_reason"],
    "volumes": ["id", "novel_id", "volume_no", "title"],
    "memories": ["id", "title", "content"],
    "projects": ["id", "name"],
}


def load_config(config_path=None):
    cfg = {"db_path": "./data/novel_memory.db"}
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg.update(json.load(f))
    return cfg


def check_schema(db_path):
    db_path = Path(db_path)

    if not db_path.exists():
        print(f"[FAIL] 数据库不存在: {db_path}")
        return False

    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()

    # Get existing tables
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    existing_tables = set(r[0] for r in cur.fetchall())

    missing_tables = []
    missing_fields = []

    for table, required_fields in REQUIRED_TABLES.items():
        if table not in existing_tables:
            missing_tables.append(table)
            continue

        cur.execute(f"PRAGMA table_info({table})")
        existing_fields = set(r[1] for r in cur.fetchall())
        for f in required_fields:
            if f not in existing_fields:
                missing_fields.append(f"{table}.{f}")

    conn.close()

    # Report
    print(f"数据库: {db_path}")
    print(f"现有表 ({len(existing_tables)}): {', '.join(sorted(existing_tables))}")

    all_ok = True

    if missing_tables:
        print(f"\n[FAIL] 缺失表 ({len(missing_tables)}):")
        for t in missing_tables:
            print(f"  - {t}")
        all_ok = False
    else:
        print(f"\n[OK] 所有必需表都存在")

    if missing_fields:
        print(f"\n[FAIL] 缺失字段 ({len(missing_fields)}):")
        for f in missing_fields:
            print(f"  - {f}")
        all_ok = False
    else:
        print(f"[OK] 所有关键字段都存在")

    if all_ok:
        print(f"\n[OK] Schema 检查通过")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Novel Forge — Schema 检查")
    parser.add_argument("--config", default=None, help="配置文件路径")
    parser.add_argument("--db-path", default=None, help="数据库路径 (覆盖配置)")
    args = parser.parse_args()

    cfg = load_config(args.config)
    if args.db_path:
        cfg["db_path"] = args.db_path

    success = check_schema(cfg["db_path"])
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
