from __future__ import annotations

import hashlib


class UsageCallTracker:
    def __init__(self, workflow_id: str, chapter_id: str):
        self._scope = f"workflow:{workflow_id}:chapter:{chapter_id}"
        self._next_sequence = 0
        self._active: dict[str, str] = {}

    def call_id(self, role: str, *, final: bool) -> str:
        call_id = self._active.get(role)
        if call_id is None:
            self._next_sequence += 1
            call_id = hashlib.sha256(f"{self._scope}:{role}:{self._next_sequence}".encode()).hexdigest()
            self._active[role] = call_id
        if final:
            del self._active[role]
        return call_id
