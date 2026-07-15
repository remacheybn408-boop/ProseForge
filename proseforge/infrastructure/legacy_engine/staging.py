from __future__ import annotations

import os
import tempfile
from pathlib import Path


def stage_text(*, root: Path, project_id: str, chapter_id: str, run_id: str, text: str) -> Path:
    target_dir = root / "artifacts" / "web-staging" / project_id / chapter_id / run_id
    target_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_dir,
        prefix=".chapter-",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    target = target_dir / "chapter.txt"
    temporary.replace(target)
    return target


def cleanup_stage(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
        parent = path.parent
        while parent.name and parent != parent.parent:
            if any(parent.iterdir()):
                break
            parent.rmdir()
            parent = parent.parent
    except OSError:
        return
