#!/usr/bin/env python3
"""
voice_memory_store.py — 封装声纹观察结果入库

Guard 只负责检测，store 负责入库。Pipeline post 调用 store。
"""

import sqlite3, json
from typing import Optional


def save_voice_observation(
    conn: sqlite3.Connection,
    novel_id: int,
    chapter_no: int,
    chapter_id: Optional[int],
    report: dict,
) -> None:
    """Save character voice guard report observations to DB."""
    cur = conn.cursor()

    # Save per-speaker observations
    for sr in report.get("speaker_reports", []):
        char_name = sr.get("speaker", "")
        if not char_name:
            continue

        cur.execute("""INSERT INTO character_voice_observations
            (novel_id, chapter_id, chapter_no, character_name,
             dialogue_count, detected_dialect_pack,
             dialect_hits_json, meme_hits_json, banned_meme_hits_json,
             english_hits_json, banned_english_hits_json,
             forbidden_hits_json, missing_signature_json,
             narration_pollution_json, profile_mismatch_json,
             warning_count, status, report_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            novel_id, chapter_id, chapter_no, char_name,
            sr.get("dialogue_count", 0),
            sr.get("expected_dialect", ""),
            json.dumps(sr.get("dialect_hits", []), ensure_ascii=False),
            json.dumps(sr.get("meme_hits", []), ensure_ascii=False),
            json.dumps(sr.get("banned_meme_hits", []), ensure_ascii=False),
            json.dumps(sr.get("english_hits", []), ensure_ascii=False),
            json.dumps(sr.get("banned_english_hits", []), ensure_ascii=False),
            json.dumps(sr.get("forbidden_hits", []), ensure_ascii=False),
            json.dumps(sr.get("missing_signature", []), ensure_ascii=False),
            json.dumps([], ensure_ascii=False),
            json.dumps(sr.get("profile_mismatch", []), ensure_ascii=False),
            len(sr.get("warnings", [])),
            "WARNING" if sr.get("warnings") else "PASS",
            json.dumps(sr, ensure_ascii=False),
        ))

    # Save narration pollution
    nar = report.get("narration_report", {})
    if nar.get("warnings"):
        cur.execute("""INSERT INTO character_voice_observations
            (novel_id, chapter_id, chapter_no, character_name,
             narration_pollution_json, warning_count, status, report_json)
            VALUES(?,?,?,?,?,?,?,?)""", (
            novel_id, chapter_id, chapter_no, "[旁白]",
            json.dumps(nar.get("warnings", []), ensure_ascii=False),
            len(nar.get("warnings", [])),
            "WARNING",
            json.dumps(nar, ensure_ascii=False),
        ))

    conn.commit()


def upsert_voice_profile(
    conn: sqlite3.Connection,
    novel_id: int,
    profile: dict,
    reason: str = "",
) -> None:
    """Upsert a single character voice profile."""
    cur = conn.cursor()
    char_name = profile.get("character_name", "")

    cur.execute("SELECT id FROM character_voice_profiles WHERE novel_id=? AND character_name=? AND phase=?",
                 (novel_id, char_name, profile.get("phase", "default")))
    existing = cur.fetchone()

    fav = json.dumps(profile.get("favorite_words", []), ensure_ascii=False)
    forb = json.dumps(profile.get("forbidden_words", []), ensure_ascii=False)
    allow_eng = json.dumps(profile.get("allowed_english", []), ensure_ascii=False)
    ban_eng = json.dumps(profile.get("banned_english", []), ensure_ascii=False)
    samples = json.dumps(profile.get("sample_lines", []), ensure_ascii=False)

    if existing:
        old = dict(cur.execute("SELECT * FROM character_voice_profiles WHERE id=?", (existing[0],)).fetchone())
        cur.execute("""UPDATE character_voice_profiles SET
            dialect_pack=?, register_pack=?, meme_pack=?, english_pack=?,
            dialect_level=?, meme_level=?, english_level=?, wenyan_level=?,
            favorite_words_json=?, forbidden_words_json=?,
            allowed_english_json=?, banned_english_json=?,
            sample_lines_json=?, notes=?, updated_at=datetime('now')
            WHERE id=?""", (
            profile.get("dialect_pack", "none"), profile.get("register_pack", "none"),
            profile.get("meme_pack", "none"), profile.get("english_pack", "none"),
            profile.get("dialect_level", 0), profile.get("meme_level", 0),
            profile.get("english_level", 0), profile.get("wenyan_level", 0),
            fav, forb, allow_eng, ban_eng, samples,
            profile.get("notes", ""), existing[0]))
        # History
        cur.execute("""INSERT INTO character_voice_history
            (novel_id, character_name, action, old_profile_json, new_profile_json, reason)
            VALUES(?,?,?,?,?,?)""", (
            novel_id, char_name, "upsert",
            json.dumps(dict(old), ensure_ascii=False, default=str),
            json.dumps(profile, ensure_ascii=False), reason))
    else:
        cur.execute("""INSERT INTO character_voice_profiles
            (novel_id, character_name, dialect_pack, register_pack, meme_pack, english_pack,
             dialect_level, meme_level, english_level, wenyan_level,
             favorite_words_json, forbidden_words_json,
             allowed_english_json, banned_english_json,
             sample_lines_json, notes, phase)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
            novel_id, char_name,
            profile.get("dialect_pack", "none"), profile.get("register_pack", "none"),
            profile.get("meme_pack", "none"), profile.get("english_pack", "none"),
            profile.get("dialect_level", 0), profile.get("meme_level", 0),
            profile.get("english_level", 0), profile.get("wenyan_level", 0),
            fav, forb, allow_eng, ban_eng, samples,
            profile.get("notes", ""), profile.get("phase", "default")))

    conn.commit()


def save_voice_examples(
    conn: sqlite3.Connection,
    novel_id: int,
    character_name: str,
    examples: list[str],
    quality: str = "good",
):
    """Save example lines for a character."""
    cur = conn.cursor()
    for text in examples:
        cur.execute("""INSERT INTO character_voice_examples
            (novel_id, character_name, example_type, text, source, quality)
            VALUES(?,?,?,?,?,?)""",
            (novel_id, character_name, "sample", text, "pipeline", quality))
    conn.commit()
