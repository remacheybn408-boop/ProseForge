#!/usr/bin/env python3
"""
voice_profile_loader.py — 统一加载角色声纹上下文

优先级:
  1. SQLite character_voice_profiles (如果 use_database_profiles=true)
  2. novels/{novel_slug}/voice_profiles.json
  3. examples/demo_novel/voice_profiles.example.json
  4. 空 profiles + warning

返回 voice_context dict，可直接传给 character_voice_guard。
"""

import sqlite3, json
from pathlib import Path
from typing import Optional


def load_voice_context(
    config: dict,
    novel_slug: str,
    db_path: str = None,
    character_names: list[str] = None,
) -> dict:
    """
    Load complete voice context for a novel.
    Returns:
      {
        "enabled": bool,
        "source": "db" | "json" | "example" | "none",
        "novel_slug": str,
        "profiles": [dict, ...],
        "packs": {pack_id: dict, ...},
        "narration_policy": dict,
        "warnings": [str, ...],
      }
    """
    voice_cfg = config.get("voice_system", {})
    if not voice_cfg.get("enabled", True):
        return _empty_context("disabled", novel_slug)

    warnings = []
    profiles = []
    packs = {}
    source = "none"
    db_path = db_path or config.get("db_path", "./data/novel_memory.db")

    # 1. Try database
    if voice_cfg.get("use_database_profiles", True) and Path(db_path).exists():
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            profiles = _load_profiles_from_db(conn, novel_slug)
            packs = _load_packs_from_db(conn)
            conn.close()
            if profiles:
                source = "db"
        except Exception as e:
            warnings.append(f"Database load failed: {e}")

    # 2. Fallback to JSON
    if not profiles:
        json_path = voice_cfg.get("voice_profiles_template", "").replace("{novel_slug}", novel_slug)
        if not json_path:
            json_path = f"novels/{novel_slug}/voice_profiles.json"
        if Path(json_path).exists():
            try:
                profiles = json.loads(Path(json_path).read_text(encoding='utf-8'))
                if not isinstance(profiles, list):
                    profiles = [profiles]
                source = "json"
            except Exception as e:
                warnings.append(f"JSON load failed ({json_path}): {e}")

    # 3. Fallback to example
    if not profiles:
        example_path = voice_cfg.get("fallback_voice_profiles", "examples/demo_novel/voice_profiles.example.json")
        if Path(example_path).exists():
            try:
                profiles = json.loads(Path(example_path).read_text(encoding='utf-8'))
                if not isinstance(profiles, list):
                    profiles = [profiles]
                source = "example"
            except Exception as e:
                warnings.append(f"Example load failed: {e}")

    # 4. Load packs if not from DB
    if not packs:
        packs_dir = voice_cfg.get("voice_packs_dir", "voice_packs")
        packs = _load_packs_from_files(packs_dir)

    # Filter to requested characters
    if character_names:
        profiles = [p for p in profiles if p.get("character_name", "") in character_names]

    narration_policy = voice_cfg.get("default_narration_policy", voice_cfg.get("narration_policy", {
        "dialect_level": 0, "meme_level": 0, "english_level": 0, "wenyan_level": 1,
    }))

    if not profiles:
        warnings.append("No voice profiles found for any character")

    return {
        "enabled": True,
        "source": source,
        "novel_slug": novel_slug,
        "profiles": profiles,
        "packs": packs,
        "narration_policy": narration_policy,
        "warnings": warnings,
    }


def _load_profiles_from_db(conn, novel_slug: str) -> list[dict]:
    cur = conn.cursor()
    cur.execute("SELECT id FROM novels WHERE slug=?", (novel_slug,))
    if not cur.fetchone():
        return []
    cur.execute("""SELECT * FROM character_voice_profiles
                   WHERE novel_id=(SELECT id FROM novels WHERE slug=?)
                   AND status='active' ORDER BY character_name""", (novel_slug,))
    profiles = []
    for r in cur.fetchall():
        profiles.append({
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
        })
    return profiles


def _load_packs_from_db(conn) -> dict:
    cur = conn.cursor()
    cur.execute("SELECT * FROM voice_packs WHERE status='active'")
    packs = {}
    for r in cur.fetchall():
        packs[r["pack_id"]] = {
            "pack_id": r["pack_id"],
            "type": r["pack_type"],
            "name": r["name"],
            "markers": json.loads(r["markers_json"] or "[]"),
            "soft_markers": json.loads(r["soft_markers_json"] or "[]"),
            "danger_markers": json.loads(r["danger_markers_json"] or "[]"),
            "allowed_contexts": json.loads(r["allowed_contexts_json"] or "[]"),
            "forbidden_contexts": json.loads(r["forbidden_contexts_json"] or "[]"),
            "max_density_per_1000_chars": r["max_density_per_1000_chars"],
            "overuse_warning_threshold": r["overuse_warning_threshold"],
        }
    return packs


def _load_packs_from_files(packs_dir: str) -> dict:
    packs = {}
    packs_path = Path(packs_dir)
    if not packs_path.exists():
        return packs
    for fp in sorted(packs_path.rglob("*.json")):
        try:
            data = json.loads(fp.read_text(encoding='utf-8'))
            pack_id = data.get("pack_id", fp.stem)
            packs[pack_id] = {
                "pack_id": pack_id,
                "type": data.get("type", ""),
                "name": data.get("name", ""),
                "markers": data.get("markers", []),
                "soft_markers": data.get("soft_markers", []),
                "danger_markers": data.get("danger_markers", []),
                "allowed_contexts": data.get("allowed_contexts", []),
                "forbidden_contexts": data.get("forbidden_contexts", []),
                "max_density_per_1000_chars": data.get("max_density_per_1000_chars", 6),
                "overuse_warning_threshold": data.get("overuse_warning_threshold", 5),
            }
        except Exception:
            pass
    return packs


def _empty_context(reason: str, novel_slug: str) -> dict:
    return {
        "enabled": False,
        "source": "none",
        "novel_slug": novel_slug,
        "profiles": [],
        "packs": {},
        "narration_policy": {},
        "warnings": [f"Voice system {reason}"],
    }


def get_profiles_for_characters(voice_context: dict, character_names: list[str]) -> list[dict]:
    """Filter voice_context.profiles to only the given character names."""
    return [p for p in voice_context.get("profiles", [])
            if p.get("character_name", "") in character_names]