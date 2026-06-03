#!/usr/bin/env python3
"""
import_voice_packs.py — 将 voice_packs/*.json 导入 SQLite voice_packs 表

用法:
  python scripts/import_voice_packs.py --config config.json
  python scripts/import_voice_packs.py --config config.json --input-dir voice_packs
  python scripts/import_voice_packs.py --config config.json --dry-run
"""

import sqlite3, json, sys, argparse
from pathlib import Path


def load_config(config_path=None):
    cfg = {"db_path": "./data/novel_memory.db"}
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg.update(json.load(f))
    return cfg


def import_packs(db_path: str, packs_dir: str, dry_run: bool = False) -> dict:
    """Scan voice_packs/**, load JSON, upsert into voice_packs table."""
    packs_dir = Path(packs_dir)
    if not packs_dir.exists():
        return {"ok": False, "error": f"voice_packs directory not found: {packs_dir}", "imported": 0}

    # Collect all JSON files
    json_files = sorted(packs_dir.rglob("*.json"))
    if not json_files:
        return {"ok": False, "error": f"No JSON files found in {packs_dir}", "imported": 0}

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    imported = 0
    updated = 0
    errors = []

    for fp in json_files:
        try:
            data = json.loads(fp.read_text(encoding='utf-8'))
        except Exception as e:
            errors.append(f"{fp.name}: JSON parse error: {e}")
            continue

        pack_id = data.get("pack_id", fp.stem)
        if not pack_id:
            errors.append(f"{fp.name}: missing pack_id")
            continue

        # Check if exists
        cur.execute("SELECT id FROM voice_packs WHERE pack_id=?", (pack_id,))
        existing = cur.fetchone()

        markers = json.dumps(data.get("markers", []), ensure_ascii=False)
        soft = json.dumps(data.get("soft_markers", []), ensure_ascii=False)
        danger = json.dumps(data.get("danger_markers", []), ensure_ascii=False)
        allowed = json.dumps(data.get("allowed_contexts", []), ensure_ascii=False)
        forbidden = json.dumps(data.get("forbidden_contexts", []), ensure_ascii=False)
        samples = json.dumps(data.get("sample_lines", []), ensure_ascii=False)

        if dry_run:
            action = "UPDATE" if existing else "INSERT"
            print(f"  [{action}] {pack_id} ({data.get('type','?')})")
            imported += 1
            continue

        if existing:
            cur.execute("""UPDATE voice_packs SET
                pack_type=?, name=?, description=?,
                markers_json=?, soft_markers_json=?, danger_markers_json=?,
                allowed_contexts_json=?, forbidden_contexts_json=?,
                sample_lines_json=?,
                max_density_per_1000_chars=?, overuse_warning_threshold=?,
                updated_at=datetime('now')
                WHERE pack_id=?""", (
                data.get("type", "dialect"), data.get("name", ""),
                data.get("description", ""),
                markers, soft, danger, allowed, forbidden, samples,
                data.get("max_density_per_1000_chars", 6),
                data.get("overuse_warning_threshold", 5),
                pack_id))
            updated += 1
        else:
            cur.execute("""INSERT INTO voice_packs
                (pack_id, pack_type, name, description,
                 markers_json, soft_markers_json, danger_markers_json,
                 allowed_contexts_json, forbidden_contexts_json,
                 sample_lines_json,
                 max_density_per_1000_chars, overuse_warning_threshold)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""", (
                pack_id, data.get("type", "dialect"), data.get("name", ""),
                data.get("description", ""),
                markers, soft, danger, allowed, forbidden, samples,
                data.get("max_density_per_1000_chars", 6),
                data.get("overuse_warning_threshold", 5)))
            imported += 1

    conn.commit()
    conn.close()

    return {
        "ok": len(errors) == 0,
        "imported": imported,
        "updated": updated,
        "errors": errors,
        "total_files": len(json_files),
    }


def main():
    parser = argparse.ArgumentParser(description="Import voice packs into SQLite")
    parser.add_argument("--config", default=None, help="config.json path")
    parser.add_argument("--db-path", default=None, help="DB path override")
    parser.add_argument("--input-dir", default="voice_packs", help="voice_packs directory")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_path = args.db_path or cfg.get("db_path", "./data/novel_memory.db")

    print(f"DB: {db_path}")
    print(f"Packs dir: {args.input_dir}")

    result = import_packs(db_path, args.input_dir, args.dry_run)
    print(f"\n结果: 导入 {result['imported']}, 更新 {result['updated']}, 文件 {result['total_files']}")
    if result["errors"]:
        for e in result["errors"]:
            print(f"  [WARN] {e}")

    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
