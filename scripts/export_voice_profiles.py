#!/usr/bin/env python3
"""
export_voice_profiles.py — 从 SQLite 导出 voice_profiles.json

用法:
  python scripts/export_voice_profiles.py --config config.json --novel-slug gewu_zhengdao
  python scripts/export_voice_profiles.py --config config.json --novel-slug gewu_zhengdao --output voice_profiles.exported.json
"""

import sqlite3, json, sys, argparse
from pathlib import Path


def load_config(config_path=None):
    cfg = {"db_path": "./data/novel_memory.db"}
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg.update(json.load(f))
    return cfg


def export_profiles(db_path: str, novel_slug: str) -> list[dict]:
    """Export character voice profiles from SQLite as JSON-compatible list."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT id FROM novels WHERE slug=?", (novel_slug,))
    if not cur.fetchone():
        conn.close()
        print(f"[WARN] Novel '{novel_slug}' not found in DB")
        return []

    cur.execute("""SELECT * FROM character_voice_profiles
                   WHERE novel_id=(SELECT id FROM novels WHERE slug=?)
                   ORDER BY character_name, phase""", (novel_slug,))
    rows = cur.fetchall()

    profiles = []
    for r in rows:
        profile = {
            "character_name": r["character_name"],
            "voice_type": r["voice_type"],
            "dialect_pack": r["dialect_pack"],
            "register_pack": r["register_pack"],
            "meme_pack": r["meme_pack"],
            "english_pack": r["english_pack"],
            "dialect_level": r["dialect_level"],
            "meme_level": r["meme_level"],
            "english_level": r["english_level"],
            "wenyan_level": r["wenyan_level"],
            "favorite_words": json.loads(r["favorite_words_json"] or "[]"),
            "forbidden_words": json.loads(r["forbidden_words_json"] or "[]"),
            "allowed_english": json.loads(r["allowed_english_json"] or "[]"),
            "banned_english": json.loads(r["banned_english_json"] or "[]"),
            "sample_lines": json.loads(r["sample_lines_json"] or "[]"),
            "notes": r["notes"],
            "phase": r["phase"],
            "source": r["source"],
        }
        profiles.append(profile)

    conn.close()
    return profiles


def main():
    parser = argparse.ArgumentParser(description="Export voice profiles from SQLite")
    parser.add_argument("--config", default=None)
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--novel-slug", required=True)
    parser.add_argument("--output", default=None, help="Output JSON file")
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_path = args.db_path or cfg.get("db_path", "./data/novel_memory.db")

    profiles = export_profiles(db_path, args.novel_slug)

    output = json.dumps(profiles, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding='utf-8')
        print(f"[OK] Exported {len(profiles)} profiles → {args.output}")
    else:
        print(output)

    print(f"\n{len(profiles)} profiles exported")


if __name__ == "__main__":
    main()
