"""Shared config helpers for human_texture guards."""
from __future__ import annotations

from pathlib import Path

from src.utils.config_utils import find_project_root


def resolve_human_texture_project_root(project_root: str | Path | None = None) -> Path:
    """Resolve the repo root without depending on fragile parent-counting."""
    anchor = project_root or Path(__file__).resolve()
    return find_project_root(anchor)


def get_genre_presets_path(project_root: str | Path | None = None) -> Path:
    """Return the canonical genre_presets.yaml location."""
    return (
        resolve_human_texture_project_root(project_root)
        / "configs"
        / "human_texture"
        / "genre_presets.yaml"
    )


def load_genre_presets(project_root: str | Path | None = None) -> dict:
    """Load genre presets as a dict, returning {} on missing/invalid files."""
    try:
        import yaml

        path = get_genre_presets_path(project_root)
        if not path.exists():
            return {}
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}
