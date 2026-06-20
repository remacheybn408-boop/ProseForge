"""Story Contract system helpers."""

from __future__ import annotations

import json
from pathlib import Path

STORY_DIR = ".story"


def resolve_story_dir(project_root: Path) -> Path:
    """Resolve the active `.story` directory for a project."""
    project_root = Path(project_root)
    try:
        ws_dir = project_root / "workspace"
        reg_file = ws_dir / "registry.json"
        if reg_file.exists():
            reg = json.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            if active:
                slot_story = ws_dir / active / STORY_DIR
                if slot_story.exists():
                    return slot_story
    except Exception:
        pass
    return project_root / STORY_DIR


__all__ = ["STORY_DIR", "resolve_story_dir"]
