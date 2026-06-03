#!/usr/bin/env python3
"""style_loader.py — Load style packs from style_packs/*.yaml"""
import yaml
from pathlib import Path
from typing import Optional, Dict, List

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_STYLE_DIR = _PROJECT_ROOT / "style_packs"
_FALLBACK = "generic"


def list_styles() -> List[str]:
    """List all available style IDs."""
    if not _STYLE_DIR.exists():
        return [_FALLBACK]
    return sorted([fp.stem for fp in _STYLE_DIR.glob("*.yaml")])


def load_style_pack(style_id: Optional[str] = None) -> Dict:
    """Load a style pack. Falls back to generic if not found."""
    sid = style_id or _FALLBACK
    path = _STYLE_DIR / f"{sid}.yaml"
    if not path.exists():
        path = _STYLE_DIR / f"{_FALLBACK}.yaml"
    if not path.exists():
        return _empty_style_pack(sid)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        data.setdefault("style_id", sid)
        return data
    except Exception:
        return _empty_style_pack(sid)


def _empty_style_pack(style_id: str) -> Dict:
    return {
        "style_id": style_id, "name": style_id, "description": "",
        "narrative_features": [], "language_features": [],
        "rhythm_features": [], "allowed_patterns": [],
        "forbidden_patterns": [], "agent_focus": [],
        "review_questions": [],
    }
