#!/usr/bin/env python3
"""genre_loader.py — Load genre packs from genre_packs/*.yaml"""
import yaml
from pathlib import Path
from typing import Optional, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_GENRE_DIR = _PROJECT_ROOT / "genre_packs"
_FALLBACK = "generic"


def list_genres() -> List[str]:
    """List all available genre IDs."""
    if not _GENRE_DIR.exists():
        return [_FALLBACK]
    return sorted([fp.stem for fp in _GENRE_DIR.glob("*.yaml")])


def load_genre_pack(genre_id: Optional[str] = None) -> Dict:
    """Load a genre pack. Falls back to generic if not found."""
    gid = genre_id or _FALLBACK
    path = _GENRE_DIR / f"{gid}.yaml"
    if not path.exists():
        path = _GENRE_DIR / f"{_FALLBACK}.yaml"
    if not path.exists():
        return _empty_genre_pack(gid)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data.setdefault("genre_id", gid)
        return data
    except Exception:
        return _empty_genre_pack(gid)


def _empty_genre_pack(genre_id: str) -> Dict:
    return {
        "genre_id": genre_id, "name": genre_id, "description": "",
        "core_promises": [], "reader_expectations": [], "common_conflicts": [],
        "chapter_rhythm": {}, "character_archetypes": [],
        "worldbuilding_checks": [], "plot_checks": [], "continuity_checks": [],
        "genre_specific_guards": [], "forbidden_patterns": [],
        "reader_pull_rules": [], "outline_validation_rules": [],
        "agent_focus": [], "review_questions": [],
    }
