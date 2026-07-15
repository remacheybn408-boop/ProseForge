from __future__ import annotations

import json

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.project import ProjectModel
from proseforge.infrastructure.database.models.remaining import WorkflowEventModel, WorkflowRunModel


class SqlAlchemyWorkflowRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, project_id: str, workflow_type: str, status: str = "QUEUED") -> WorkflowRunModel:
        run = WorkflowRunModel(id=new_id(), project_id=project_id, workflow_type=workflow_type, status=status)
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
        run.status = status
        await self.append_event(run.id, status, {"status": status})

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
