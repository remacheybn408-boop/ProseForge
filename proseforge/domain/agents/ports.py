from __future__ import annotations
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

@dataclass(frozen=True)
class AgentRunRequest:
    run_id: str
    project_id: str
    goal_hash: str
    graph_revision: int

@dataclass(frozen=True)
class AgentRunHandle:
    run_id: str
    status: str

@dataclass(frozen=True)
class AgentEvent:
    sequence: int
    event: str
    node_id: str | None = None

class AgentOrchestratorPort(Protocol):
    async def start(self, request: AgentRunRequest) -> AgentRunHandle: ...
    async def pause(self, run_id: str) -> None: ...
    async def resume(self, run_id: str) -> None: ...
    async def cancel(self, run_id: str) -> None: ...
    async def retry(self, run_id: str, node_id: str | None = None) -> None: ...
    async def events(self, run_id: str, after: int = 0) -> AsyncIterator[AgentEvent]: ...
