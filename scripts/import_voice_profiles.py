#!/usr/bin/env python3
"""
import_voice_profiles.py — 将 voice_profiles.json 导入 SQLite

用法:
  python scripts/import_voice_profiles.py --config config.json --novel-slug gewu_zhengdao --input voice_profiles.json
  python scripts/import_voice_profiles.py --config config.json --novel-slug gewu_zhengdao --input voice_profiles.json --dry-run
  python scripts/import_voice_profiles.py --config config.json --novel-slug gewu_zhengdao --input voice_profiles.json --replace
"""

import sqlite3, json, sys, argparse
from pathlib import Path


def load_config(config_path=None):
    cfg = {"db_path": "./data/novel_memory.db"}
    if config_path and Path(config_path).exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg.update(json.load(f))
    return cfg


def import_profiles(db_path: str, novel_slug: str, input_path: str, dry_run: bool = False, replace: bool = False) -> dict:
    """Import character voice profiles from JSON into SQLite."""
    input_path = Path(input_path)
    if not input_path.exists():
        return {"ok": False, "error": f"File not found: {input_path}", "imported": 0}

    try:
        profiles = json.loads(input_path.read_text(encoding='utf-8'))
    except Exception as e:
        return {"ok": False, "error": f"JSON parse error: {e}", "imported": 0}

    if not isinstance(profiles, list):
        profiles = [profiles]

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Find novel_id
    cur.execute("SELECT id FROM novels WHERE slug=?", (novel_slug,))
    novel_row = cur.fetchone()
    if not novel_row:
        conn.close()
        return {"ok": False, "error": f"Novel slug '{novel_slug}' not found in novels table", "imported": 0}
    novel_id = novel_row[0]

    imported = 0
    updated = 0
    examples_added = 0
    warnings = []

    for profile in profiles:
        char_name = profile.get("character_name", "")
        if not char_name:
            warnings.append("profile missing character_name")
            continue

        # Try to match characters table
        cur.execute("SELECT id FROM characters WHERE novel_id=? AND name=?", (novel_id, char_name))
        char_row = cur.fetchone()
        char_id = char_row[0] if char_row else None
        if not char_id:
            warnings.append(f"character not found in characters table: {char_name}")

        fav = json.dumps(profile.get("favorite_words", []), ensure_ascii=False)
        forb = json.dumps(profile.get("forbidden_words", []), ensure_ascii=False)
        allow_eng = json.dumps(profile.get("allowed_english", []), ensure_ascii=False)
        ban_eng = json.dumps(profile.get("banned_english", []), ensure_ascii=False)
        samples = json.dumps(profile.get("sample_lines", []), ensure_ascii=False)

        phase = profile.get("phase", "default")

        if dry_run:
            action = "UPDATE" if replace else "UPSERT"
            print(f"  [{action}] {char_name} (phase={phase})")
            imported += 1
            continue

        # Check existing
        cur.execute("SELECT id, favorite_words_json, forbidden_words_json FROM character_voice_profiles WHERE novel_id=? AND character_name=? AND phase=?",
                     (novel_id, char_name, phase))
        existing = cur.fetchone()

        if existing:
            old_fav = existing[1]
            old_forb = existing[2]
            prof_id = existing[0]

            cur.execute("""UPDATE character_voice_profiles SET
                character_id=?, voice_type=?, dialect_pack=?, register_pack=?,
                meme_pack=?, english_pack=?,
                dialect_level=?, meme_level=?, english_level=?, wenyan_level=?,
                favorite_words_json=?, forbidden_words_json=?,
                allowed_english_json=?, banned_english_json=?,
                sample_lines_json=?, notes=?, source=?,
                updated_at=datetime('now')
                WHERE id=?""", (
                char_id,
                profile.get("voice_type", ""),
                profile.get("dialect_pack", "none"),
                profile.get("register_pack", "none"),
                profile.get("meme_pack", "none"),
                profile.get("english_pack", "none"),
                profile.get("dialect_level", 0),
                profile.get("meme_level", 0),
                profile.get("english_level", 0),
                profile.get("wenyan_level", 0),
                fav, forb, allow_eng, ban_eng, samples,
                profile.get("notes", ""),
                profile.get("source", "manual"),
                prof_id))

            # Record history
            cur.execute("""INSERT INTO character_voice_history
                (novel_id, character_name, action, old_profile_json, new_profile_json, reason)
                VALUES(?,?,?,?,?,?)""", (
                novel_id, char_name, "update",
                json.dumps({"favorite_words": old_fav, "forbidden_words": old_forb}, ensure_ascii=False),
                json.dumps(profile, ensure_ascii=False),
                "manual import"))
            updated += 1
        else:
            cur.execute("""INSERT INTO character_voice_profiles
                (novel_id, character_id, character_name, voice_type,
                 dialect_pack, register_pack, meme_pack, english_pack,
                 dialect_level, meme_level, english_level, wenyan_level,
                 favorite_words_json, forbidden_words_json,
                 allowed_english_json, banned_english_json,
                 sample_lines_json, notes, phase, source)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                novel_id, char_id, char_name,
                profile.get("voice_type", ""),
                profile.get("dialect_pack", "none"),
                profile.get("register_pack", "none"),
                profile.get("meme_pack", "none"),
                profile.get("english_pack", "none"),
                profile.get("dialect_level", 0),
                profile.get("meme_level", 0),
                profile.get("english_level", 0),
                profile.get("wenyan_level", 0),
                fav, forb, allow_eng, ban_eng, samples,
                profile.get("notes", ""),
                phase,
                profile.get("source", "manual")))
            imported += 1

        # Save sample lines as examples
        for line in profile.get("sample_lines", []):
            cur.execute("""INSERT INTO character_voice_examples
                (novel_id, character_name, example_type, text, source, quality)
                VALUES(?,?,?,?,?,?)""",
                (novel_id, char_name, "sample", line, "manual import", "good"))
            examples_added += 1

    conn.commit()
    conn.close()

    return {
        "ok": True,
        "imported": imported,
        "updated": updated,
        "examples_inserted": examples_added,
        "warnings": warnings,
    }


def main():
    parser = argparse.ArgumentParser(description="Import voice profiles into SQLite")
    parser.add_argument("--config", default=None, help="config.json path")
    parser.add_argument("--db-path", default=None)
    parser.add_argument("--novel-slug", required=True, help="Novel slug")
    parser.add_argument("--input", required=True, help="voice_profiles.json path")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace", action="store_true", help="Replace existing profiles")
    args = parser.parse_args()

    cfg = load_config(args.config)
    db_path = args.db_path or cfg.get("db_path", "./data/novel_memory.db")

    print(f"DB: {db_path}")
    print(f"Novel: {args.novel_slug}")
    print(f"Input: {args.input}")

    result = import_profiles(db_path, args.novel_slug, args.input, args.dry_run, args.replace)
    print(f"\n结果: 导入 {result['imported']}, 更新 {result['updated']}, 例句 {result['examples_inserted']}")
    for w in result.get("warnings", []):
        print(f"  [WARN] {w}")

    sys.exit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
