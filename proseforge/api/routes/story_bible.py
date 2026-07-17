from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.models.project import ProjectModel
from proseforge.infrastructure.database.models.story_bible import StoryBibleEntryModel
from proseforge.domain.story_bible.entities import VALID_KINDS
from proseforge.domain.common.ids import new_id

router = APIRouter(prefix="/api/v2", tags=["story-bible"])


class FactRequest(BaseModel):
    kind: str
    key: str = Field(min_length=1, max_length=200)
    value: dict[str, object]
    pinned: bool = False


async def _owns(uow, project_id: str, user_id: str) -> bool:
    return await uow.session.scalar(select(ProjectModel.id).where(ProjectModel.id == project_id, ProjectModel.owner_id == user_id)) is not None


@router.get("/projects/{project_id}/story-bible")
async def list_facts(project_id: str, user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work)):
    async with uow:
        if not await _owns(uow, project_id, user.id): raise HTTPException(status_code=404, detail="project not found")
        rows = (await uow.session.scalars(select(StoryBibleEntryModel).where(StoryBibleEntryModel.project_id == project_id, StoryBibleEntryModel.status == "active").order_by(StoryBibleEntryModel.kind, StoryBibleEntryModel.key))).all()
        return [_response(row) for row in rows]


@router.post("/projects/{project_id}/story-bible/entries", status_code=201)
async def create_fact(project_id: str, payload: FactRequest, user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work)):
    if payload.kind not in VALID_KINDS: raise HTTPException(status_code=422, detail="unsupported story bible kind")
    async with uow:
        if not await _owns(uow, project_id, user.id): raise HTTPException(status_code=404, detail="project not found")
        now = datetime.now(UTC)
        row = StoryBibleEntryModel(id=new_id(), project_id=project_id, kind=payload.kind, key=payload.key, value_json=json.dumps(payload.value, ensure_ascii=False), pinned=payload.pinned, created_at=now, updated_at=now)
        uow.session.add(row); await uow.commit(); return _response(row)


@router.post("/story-bible/{entry_id}/pin")
async def pin_fact(entry_id: str, user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work)):
    async with uow:
        row = await uow.session.get(StoryBibleEntryModel, entry_id)
        if row is None or not await _owns(uow, row.project_id, user.id): raise HTTPException(status_code=404, detail="fact not found")
        row.pinned = not row.pinned; row.updated_at = datetime.now(UTC); await uow.commit(); return _response(row)


def _response(row: StoryBibleEntryModel) -> dict[str, object]:
    return {"id": row.id, "project_id": row.project_id, "kind": row.kind, "key": row.key, "value": json.loads(row.value_json), "status": row.status, "confidence": row.confidence, "source": row.source, "pinned": row.pinned, "version": row.version}
