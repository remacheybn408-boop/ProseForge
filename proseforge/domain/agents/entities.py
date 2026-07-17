from __future__ import annotations
from dataclasses import dataclass
from datetime import UTC, datetime

@dataclass
class AgentRun:
    id: str
    project_id: str
    goal_hash: str
    graph_revision: int
    status: str = "PENDING"
    checkpoint_id: str | None = None
    terminal_reason: str | None = None
    updated_at: datetime = None

    def __post_init__(self):
        if self.updated_at is None: self.updated_at = datetime.now(UTC)
