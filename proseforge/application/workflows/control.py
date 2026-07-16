from __future__ import annotations

import json
from dataclasses import dataclass

from proseforge.domain.workflow.state import ALLOWED_TRANSITIONS


TASK_NAME = "proseforge.workflows.generate_novel"


@dataclass(frozen=True)
class WorkflowControlResult:
    run: object
    task_id: str | None = None

    @property
    def status(self) -> str:
        return str(self.run.status)


def workflow_command(*, user_id: str, chapter_numbers: list[int], provider: str, model: str, editor_model: str) -> dict[str, object]:
    return {
        "user_id": user_id,
        "chapter_numbers": chapter_numbers,
        "provider": provider,
        "model": model,
        "editor_model": editor_model,
    }


class WorkflowControlService:
    def __init__(self, uow, queue):
        self.uow = uow
        self.queue = queue

    async def execute(self, workflow_id: str, user_id: str, action: str) -> WorkflowControlResult:
        targets = {"pause": "PAUSED", "cancel": "CANCELLED"}
        run = await self.uow.workflows.get_owned(workflow_id, user_id)
        if run is None:
            raise LookupError("workflow not found")

        task_id = None
        if action in {"resume", "retry"}:
            command = await self.uow.workflows.get_command(run)
            if command is None:
                raise ValueError("workflow has no durable command")
            target = "QUEUED" if "QUEUED" in ALLOWED_TRANSITIONS.get(run.status, set()) else "RETRYING"
            payload = {"workflow_id": run.id, **command}
            if target not in ALLOWED_TRANSITIONS.get(run.status, set()):
                raise ValueError(f"invalid workflow transition: {run.status} -> {target}")
            await self.uow.workflows.transition(run, target)
            await self.uow.commit()
            task_id = await self.queue.enqueue(TASK_NAME, payload)
            await self.uow.workflows.set_task(run, task_id)
            await self.uow.commit()
            return WorkflowControlResult(run=run, task_id=task_id)

        target = targets.get(action)
        if target is None:
            raise LookupError("workflow action not found")
        if target not in ALLOWED_TRANSITIONS.get(run.status, set()):
            raise ValueError(f"invalid workflow transition: {run.status} -> {target}")
        await self.uow.workflows.transition(run, target)
        await self.uow.commit()
        return WorkflowControlResult(run=run)


def decode_checkpoint(checkpoint: str | None) -> dict[str, object]:
    if not checkpoint:
        return {}
    try:
        value = json.loads(checkpoint)
    except json.JSONDecodeError:
        return {"phase": checkpoint}
    return value if isinstance(value, dict) else {}
