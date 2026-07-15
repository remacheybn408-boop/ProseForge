from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.project import ProjectModel
from proseforge.infrastructure.database.models.remaining import WorkflowEventModel, WorkflowRunModel
from proseforge.domain.workflow.state import ALLOWED_TRANSITIONS


class SqlAlchemyWorkflowRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: str, workflow_type: str, status: str = "QUEUED", cost_limit: float = 0.0) -> WorkflowRunModel:
        run = WorkflowRunModel(id=new_id(), project_id=project_id, workflow_type=workflow_type, status=status, cost_limit=cost_limit)
        self.session.add(run)
        await self.session.flush()
        await self.append_event(run.id, status, {"status": status})
        return run

    async def get_owned(self, workflow_id: str, owner_id: str) -> WorkflowRunModel | None:
        return await self.session.scalar(
            select(WorkflowRunModel)
            .join(ProjectModel, ProjectModel.id == WorkflowRunModel.project_id)
            .where(WorkflowRunModel.id == workflow_id, ProjectModel.owner_id == owner_id)
        )

    async def transition(self, run: WorkflowRunModel, status: str) -> None:
        if status not in ALLOWED_TRANSITIONS.get(run.status, set()):
            raise ValueError(f"invalid workflow transition: {run.status} -> {status}")
        run.status = status
        await self.append_event(run.id, status, {"status": status})

    async def acquire_lease(self, run: WorkflowRunModel, owner: str, ttl_seconds: int = 60) -> bool:
        now = datetime.now(UTC)
        if run.lease_owner and run.lease_expires_at and run.lease_expires_at > now:
            return False
        run.lease_owner = owner
        run.lease_expires_at = now + timedelta(seconds=ttl_seconds)
        run.heartbeat_at = now
        await self.session.flush()
        return True

    async def heartbeat(self, run: WorkflowRunModel, owner: str, ttl_seconds: int = 60) -> None:
        if run.lease_owner != owner:
            raise PermissionError("workflow lease is not owned by caller")
        now = datetime.now(UTC)
        run.heartbeat_at = now
        run.lease_expires_at = now + timedelta(seconds=ttl_seconds)
        await self.session.flush()

    async def checkpoint(self, run: WorkflowRunModel, owner: str, checkpoint: str, estimated_cost: float = 0.0) -> None:
        if run.lease_owner != owner:
            raise PermissionError("workflow lease is not owned by caller")
        projected = float(run.estimated_cost or 0) + estimated_cost
        if run.cost_limit and projected > run.cost_limit:
            raise ValueError("workflow cost limit exceeded")
        run.checkpoint = checkpoint
        run.estimated_cost = projected
        await self.session.flush()

    async def recover_expired(self) -> int:
        now = datetime.now(UTC)
        rows = await self.session.scalars(select(WorkflowRunModel).where(WorkflowRunModel.status == "RUNNING", WorkflowRunModel.lease_expires_at <= now))
        recovered = 0
        for run in rows:
            run.status = "RECOVERING"
            run.lease_owner = None
            run.lease_expires_at = None
            await self.append_event(run.id, "RECOVERING", {"status": "RECOVERING", "reason": "lease_expired"})
            recovered += 1
        await self.session.flush()
        return recovered

    async def append_event(self, workflow_id: str, event_type: str, payload: dict[str, object]) -> None:
        sequence = await self.session.scalar(
            select(func.coalesce(func.max(WorkflowEventModel.sequence_no), 0)).where(
                WorkflowEventModel.workflow_run_id == workflow_id
            )
        )
        self.session.add(
            WorkflowEventModel(
                id=new_id(),
                workflow_run_id=workflow_id,
                sequence_no=int(sequence or 0) + 1,
                event_type=event_type,
                payload=json.dumps(payload, ensure_ascii=False),
            )
        )
        await self.session.flush()

    async def events(self, workflow_id: str, after: int = 0) -> list[dict[str, object]]:
        rows = await self.session.scalars(
            select(WorkflowEventModel)
            .where(WorkflowEventModel.workflow_run_id == workflow_id, WorkflowEventModel.sequence_no > after)
            .order_by(WorkflowEventModel.sequence_no)
        )
        return [
            {"id": row.sequence_no, "event": row.event_type, "data": json.loads(row.payload)}
            for row in rows
        ]
