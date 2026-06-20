from __future__ import annotations

from src.voice.voice_pack_validator import validate_all_packs, validate_voice_pack


def test_validate_voice_pack_accepts_minimal_valid_pack():
    result = validate_voice_pack(
        {
            "pack_id": "hero-voice",
            "name": "Hero Voice",
            "role_type": "lead",
            "_source_file": "packs/voice/hero.yaml",
            "tone": {"emotion_range": {"calm": 0.5}},
            "narration_levels": {"dialect_level": 1},
        }
    )
    assert result.is_valid is True
    assert result.source_file == "packs/voice/hero.yaml"


def test_validate_voice_pack_flags_missing_and_invalid_fields():
    result = validate_voice_pack(
        {
            "pack_id": "",
            "name": "Broken Voice",
            "tone": {"emotion_range": {"unknown": 2.0}},
            "narration_levels": {"dialect_level": 9},
        }
    )
    assert result.is_valid is False
    assert any(err.field == "pack_id" for err in result.errors)
    assert any(err.field == "role_type" for err in result.errors)
    assert any(err.severity == "warning" for err in result.warnings)


def test_validate_all_packs_catches_duplicate_pack_ids():
    results = validate_all_packs(
        [
            {"pack_id": "dup", "name": "One", "role_type": "lead"},
            {"pack_id": "dup", "name": "Two", "role_type": "support"},
        ]
    )
    assert len(results) == 2
    assert results[1].is_valid is False
    assert any("Duplicate pack_id" in err.message for err in results[1].errors)
