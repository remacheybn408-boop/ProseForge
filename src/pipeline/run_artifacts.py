"""Stable, per-operation artifact directories."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class RunArtifacts:
    run_id: str
    directory: Path


def create_run_artifacts(root: str | Path, *, chapter_no: int, operation: str) -> RunArtifacts:
    run_id = f"run_{uuid4().hex}"
    directory = (
        Path(root) / "runs" / operation / f"chapter_{chapter_no:03d}" / run_id
    )
    directory.mkdir(parents=True, exist_ok=False)
    return RunArtifacts(run_id=run_id, directory=directory)
