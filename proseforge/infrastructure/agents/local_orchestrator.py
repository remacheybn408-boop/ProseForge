from __future__ import annotations
from collections import defaultdict
from proseforge.domain.agents.ports import AgentEvent, AgentRunHandle, AgentRunRequest

class LocalOrchestrator:
    def __init__(self): self.runs = {}; self._events = defaultdict(list)
    async def start(self, request: AgentRunRequest) -> AgentRunHandle:
        if request.run_id in self.runs: return self.runs[request.run_id]
        handle = AgentRunHandle(request.run_id, "PENDING"); self.runs[request.run_id] = handle; self._events[request.run_id].append(AgentEvent(1, "run.created")); return handle
    async def _set(self, run_id, status):
        current = self.runs[run_id]; self.runs[run_id] = AgentRunHandle(run_id, status); self._events[run_id].append(AgentEvent(len(self._events[run_id]) + 1, f"run.{status.lower()}"))
    async def pause(self, run_id): await self._set(run_id, "PAUSED")
    async def resume(self, run_id): await self._set(run_id, "RUNNING")
    async def cancel(self, run_id): await self._set(run_id, "CANCELLED")
    async def retry(self, run_id, node_id=None): await self._set(run_id, "RUNNING")
    async def events(self, run_id, after=0):
        for event in self._events[run_id]:
            if event.sequence > after: yield event
