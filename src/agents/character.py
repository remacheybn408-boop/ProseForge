"""Compatibility imports for the migrated character analyzer."""

from pathlib import Path

from proseforge.domain.quality.analyzers.character_analyzer import (
    CharacterAnalyzer,
    _load_packs_from_files,
    get_profiles_for_characters,
    load_voice_context,
)
from src.guards.human_texture import character_psychology_crud


class CharacterAgent(CharacterAnalyzer):
    """Legacy compatibility class retaining the old psychology hook."""

    @staticmethod
    def _load_character_psychologies() -> list:
        project_root = Path(__file__).resolve().parents[2]
        return character_psychology_crud.list_character_psychologies(project_root)

__all__ = [
    "CharacterAgent",
    "CharacterAnalyzer",
    "_load_packs_from_files",
    "get_profiles_for_characters",
    "load_voice_context",
]
