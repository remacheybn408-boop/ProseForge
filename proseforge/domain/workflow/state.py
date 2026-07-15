from __future__ import annotations

from dataclasses import dataclass


ALLOWED_TRANSITIONS = {
    "CREATED": {"WAITING_USER", "QUEUED", "CANCELLED"}, "WAITING_USER": {"QUEUED", "CANCELLED"},
    "QUEUED": {"RUNNING", "CANCELLED"}, "RUNNING": {"PAUSED", "RETRYING", "COMPLETED", "FAILED", "CANCELLED", "RECOVERING"},
    "PAUSED": {"QUEUED", "CANCELLED"}, "RETRYING": {"RUNNING", "FAILED", "PAUSED"}, "RECOVERING": {"QUEUED", "PAUSED", "FAILED"},
    "COMPLETED": set(), "FAILED": {"QUEUED"}, "CANCELLED": set(),
}


class InvalidWorkflowTransition(ValueError):
    pass


@dataclass
class WorkflowState:
    status: str = "CREATED"

    def transition(self, target: str) -> None:
        if target not in ALLOWED_TRANSITIONS.get(self.status, set()):
            raise InvalidWorkflowTransition(f"{self.status} -> {target}")
        self.status = target
