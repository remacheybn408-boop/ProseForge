#!/usr/bin/env python3
"""
repair_slot_schema.py — 把遗留 slot 的 novel.db 补齐到当前完整 schema

背景:
  用旧 schema 建的 novel.db 可能缺表（如 writing_rules / arc_character_states 等），
  导致 nf_pipeline 运行时报 `no such table: ...`。本脚本幂等地把每个 slot 的库补齐
  到 database/schema.sql + migrations 定义的完整 schema，只加缺失的表、不动既有数据。

策略:
  1. 扫描 workspace/registry.json 中所有 slot
  2. 对每个 slot 的 novel.db，对比期望表名，报告缺哪些
  3. --apply 时：先把 novel.db 复制到 <slot>/backups/novel.db.<ts>.bak，再 ensure_slot_schema

默认 dry-run。需要 --apply 才会真改。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# 独立脚本：把仓库根加入 sys.path，以便复用 src.* 的共享实现
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
from src.db.init_db import expected_table_names  # noqa: E402
from src.db.slot_manager import SlotManager  # noqa: E402


def _have_tables(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    try:
        conn = sqlite3.connect(db_path)
        try:
            return {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
        finally:
            conn.close()
    except sqlite3.Error:
        return set()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--project-root", default=str(_REPO_ROOT),
        help="项目根目录 (默认: 仓库根)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="真正补齐 schema（默认 dry-run）",
    )
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    workspace = project_root / "workspace"
    registry_path = workspace / "registry.json"
    if not registry_path.exists():
        print(f"[ERR] registry.json 不存在: {registry_path}", file=sys.stderr)
        return 1

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    slots = registry.get("slots", [])
    if not slots:
        print("(registry 中无 slot)")
        return 0

    expected = expected_table_names(project_root)
    mgr = SlotManager(project_root)

    print(f"\n=== schema 检查 (workspace = {workspace}) ===")
    print(f"期望普通表数: {len(expected)}")
    need_fix: list[tuple[str, list[str]]] = []
    for slot in slots:
        slot_id = slot.get("id", "")
        if not slot_id:
            continue
        db_path = workspace / slot_id / "novel.db"
        if not db_path.exists():
            print(f"  {slot_id:30s}  skip: 无 novel.db")
            continue
        missing = sorted(expected - _have_tables(db_path))
        if missing:
            need_fix.append((slot_id, missing))
            print(f"  {slot_id:30s}  缺 {len(missing)} 表: {', '.join(missing)}")
        else:
            print(f"  {slot_id:30s}  OK (schema 已最新)")

    if not need_fix:
        print("\n[DONE] 所有 slot schema 均已最新，无需修复。")
        return 0

    if not args.apply:
        print(
            f"\n[DRY-RUN] {len(need_fix)} 个 slot 需补齐。加 --apply 真正执行"
            f"（会先备份 novel.db）。"
        )
        return 0

    print("\n=== 开始补齐 ===")
    fixed = 0
    for slot_id, missing in need_fix:
        db_path = workspace / slot_id / "novel.db"
        # 备份
        backup_dir = workspace / slot_id / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = backup_dir / f"novel.db.{ts}.bak"
        shutil.copy2(db_path, backup)
        # 补齐
        ok = mgr.ensure_slot_schema(slot_id)
        still_missing = sorted(expected - _have_tables(db_path))
        if ok and not still_missing:
            fixed += 1
            print(f"  [OK] {slot_id}: 补齐 {len(missing)} 表（备份 {backup.name}）")
        else:
            print(
                f"  [FAIL] {slot_id}: ensure 返回 {ok}，仍缺 {still_missing}",
                file=sys.stderr,
            )

    print(f"\n[DONE] {fixed}/{len(need_fix)} 个 slot 已补齐。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
