from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime

@dataclass(frozen=True)
class Checkpoint:
    run_id: str
    node_id: str
    cursor: int
    output_refs: tuple[str, ...]
    created_at: datetime

def make_checkpoint(run_id: str, node_id: str, cursor: int, output_refs: tuple[str, ...] = ()) -> Checkpoint:
    return Checkpoint(run_id, node_id, cursor, output_refs, datetime.now(UTC))
