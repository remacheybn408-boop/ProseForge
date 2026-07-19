#!/usr/bin/env python3
"""
migrate_slot_names.py — 一次性把 workspace/slot_NNN/ 改名为 workspace/<novel-slug>/

策略:
  1. 扫描 workspace/registry.json 中所有 slot
  2. 对每个 slot 打开 novel.db，读 SELECT slug, title FROM novels LIMIT 1
  3. 优先用 novels.slug 作为新名；否则用 _title_to_slug(novels.title)
  4. 空 slot（无 novels 行）跳过（保留原名）
  5. 重名 → 加 _2 / _3 后缀
  6. shutil.move 改目录名，同步更新 registry.json 的 slots[].id 和 active_slot

默认 dry-run。需要 --apply 才会真改。
"""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path

# 独立脚本：把仓库根加入 sys.path，以便复用 src.* 的共享实现
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.utils.slug import title_to_slug
from src.db._conn import connect_sqlite


def read_novel(db_path: Path) -> dict | None:
    if not db_path.exists():
        return None
    try:
        conn = connect_sqlite(db_path, read_only=True)
        try:
            cur = conn.execute("SELECT slug, title FROM novels LIMIT 1")
            row = cur.fetchone()
            if row is None:
                return None
            return {"slug": row[0] or "", "title": row[1] or ""}
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def derive_new_name(slug: str, title: str, taken: set[str]) -> str:
    base = title_to_slug(slug) if slug.strip() else title_to_slug(title)
    candidate = base
    n = 2
    while candidate in taken:
        candidate = f"{base}_{n}"
        n += 1
    return candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--workspace", default="workspace",
                        help="workspace 目录路径 (默认: workspace)")
    parser.add_argument("--apply", action="store_true",
                        help="真正执行改名（默认 dry-run）")
    args = parser.parse_args()

    workspace = Path(args.workspace).resolve()
    if not workspace.exists():
        print(f"[ERR] workspace 不存在: {workspace}", file=sys.stderr)
        return 1

    registry_path = workspace / "registry.json"
    if not registry_path.exists():
        print(f"[ERR] registry.json 不存在: {registry_path}", file=sys.stderr)
        return 1

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    slots = registry.get("slots", [])
    active = registry.get("active_slot", "")

    plan = []
    taken = {s.get("id", "") for s in slots}
    for slot in slots:
        old_id = slot.get("id", "")
        if not old_id:
            continue
        db_path = workspace / old_id / "novel.db"
        novel = read_novel(db_path)
        if novel is None:
            plan.append((old_id, None, "skip: empty slot (no novels row)"))
            continue
        # 临时从 taken 移除自己，避免和自己冲突
        scratch = taken - {old_id}
        new_id = derive_new_name(novel["slug"], novel["title"], scratch)
        if new_id == old_id:
            plan.append((old_id, None, f"skip: already named '{new_id}'"))
            continue
        if (workspace / new_id).exists():
            plan.append((old_id, None, f"skip: target '{new_id}' already on disk"))
            continue
        plan.append((old_id, new_id, f"rename ({novel['title']!r})"))
        taken = (taken - {old_id}) | {new_id}

    # 摘要
    print(f"\n=== 迁移计划 (workspace = {workspace}) ===")
    if not plan:
        print("(无变更)")
        return 0
    for old, new, note in plan:
        arrow = "→" if new else " "
        target = new or "-"
        print(f"  {old:30s} {arrow} {target:30s}  {note}")

    if not args.apply:
        print(f"\n[DRY-RUN] {sum(1 for _,n,_ in plan if n)} 个 slot 将被改名。加 --apply 真正执行。")
        return 0

    # 真改
    print("\n=== 开始迁移 ===")
    renamed = 0
    for old, new, _ in plan:
        if new is None:
            continue
        src = workspace / old
        dst = workspace / new
        try:
            shutil.move(str(src), str(dst))
        except OSError as e:
            print(f"  [ERR] {old} → {new}: {e}", file=sys.stderr)
            continue
        # 更新 registry
        for slot in slots:
            if slot.get("id") == old:
                slot["id"] = new
        if active == old:
            registry["active_slot"] = new
            active = new
        renamed += 1
        print(f"  [OK] {old} → {new}")

    registry["slots"] = slots
    registry_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n[DONE] {renamed} 个 slot 已迁移，registry.json 已更新。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
