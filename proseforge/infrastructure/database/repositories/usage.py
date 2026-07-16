from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.common.ids import new_id
from proseforge.domain.usage import UsageDelta
from proseforge.infrastructure.database.models.usage import ModelUsageRecordModel
from proseforge.infrastructure.database.models.remaining import WorkflowRunModel


class SqlAlchemyUsageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def record(self, *, user_id: str, provider: str, model_id: str, call_id: str, delta: UsageDelta, project_id: str | None = None, conversation_id: str | None = None, message_id: str | None = None, workflow_run_id: str | None = None, workflow_step: str | None = None, provider_request_id: str | None = None, cost_usd: float | None = None, latency_ms: float | None = None, metadata: dict[str, object] | None = None) -> ModelUsageRecordModel:
        row = await self.session.scalar(select(ModelUsageRecordModel).where(ModelUsageRecordModel.call_id == call_id))
        previous_total = int(row.total_tokens or 0) if row is not None else 0
        if row is None:
            row = ModelUsageRecordModel(id=new_id(), user_id=user_id, provider=provider, model_id=model_id, call_id=call_id)
            self.session.add(row)
        row.project_id = project_id
        row.conversation_id = conversation_id
        row.message_id = message_id
        row.workflow_run_id = workflow_run_id
        row.workflow_step = workflow_step
        row.provider_request_id = provider_request_id or delta.provider_request_id
        row.input_tokens = delta.input_tokens
        row.output_tokens = delta.output_tokens
        row.cached_input_tokens = delta.cached_input_tokens
        row.reasoning_tokens = delta.reasoning_tokens
        row.total_tokens = delta.total_tokens
        row.usage_source = delta.source
        row.is_final = delta.final
        row.cost_usd = cost_usd
        row.latency_ms = latency_ms
        row.metadata_json = json.dumps(metadata if metadata is not None else delta.raw_metadata, ensure_ascii=False)
        if workflow_run_id:
            workflow = await self.session.get(WorkflowRunModel, workflow_run_id)
            if workflow is not None:
                workflow.used_tokens = max(0, int(workflow.used_tokens or 0) + delta.total_tokens - previous_total)
        await self.session.flush()
        return row

    async def list_for_user(self, user_id: str, *, project_id: str | None = None, conversation_id: str | None = None, workflow_run_id: str | None = None, message_id: str | None = None, limit: int = 100) -> list[ModelUsageRecordModel]:
        query = select(ModelUsageRecordModel).where(ModelUsageRecordModel.user_id == user_id).order_by(ModelUsageRecordModel.created_at.desc()).limit(max(1, min(limit, 500)))
        if project_id:
            query = query.where(ModelUsageRecordModel.project_id == project_id)
        if conversation_id:
            query = query.where(ModelUsageRecordModel.conversation_id == conversation_id)
        if workflow_run_id:
            query = query.where(ModelUsageRecordModel.workflow_run_id == workflow_run_id)
        if message_id:
            query = query.where(ModelUsageRecordModel.message_id == message_id)
        return list(await self.session.scalars(query))
