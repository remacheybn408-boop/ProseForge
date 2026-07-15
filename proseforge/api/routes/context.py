from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1", tags=["context"])


class ContextCreateRequest(BaseModel):
    source_type: str = Field(default="manual", min_length=1, max_length=64)
    content: str = Field(min_length=1, max_length=100000)
    source_id: str = "manual"


class ContextUpdateRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=100000)
    pinned: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    excluded: bool | None = None


def _response(item) -> dict[str, object]:
    return {
        "id": item.id, "project_id": item.project_id, "source_type": item.source_type,
        "source_id": item.source_id, "content": item.content, "pinned": item.pinned,
        "priority": item.priority, "excluded": item.excluded, "provenance": json.loads(item.provenance or "{}"),
    }


@router.get("/projects/{project_id}/context")
async def list_context(project_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        items = await uow.context.list_owned(project_id, user.id)
        return {"items": [_response(item) for item in items], "used_tokens": sum(len(item.content) // 2 for item in items if not item.excluded), "context_window": 128000}


@router.post("/projects/{project_id}/context/items", status_code=status.HTTP_201_CREATED)
async def add_context(project_id: str, payload: ContextCreateRequest, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        item = await uow.context.add(project_id, payload.source_type, payload.content, payload.source_id)
        await uow.commit()
        return _response(item)


@router.patch("/context/items/{item_id}")
async def update_context(item_id: str, payload: ContextUpdateRequest, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        item = await uow.context.get_owned(item_id, user.id)
        if item is None:
            raise HTTPException(status_code=404, detail="context item not found")
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(item, key, value)
        await uow.commit()
        return _response(item)


@router.delete("/context/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_context(item_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> None:
    async with uow:
        item = await uow.context.get_owned(item_id, user.id)
        if item is None:
            raise HTTPException(status_code=404, detail="context item not found")
        await uow.session.delete(item)
        await uow.commit()


@router.post("/projects/{project_id}/context/compile")
async def compile_context(project_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        items = await uow.context.list_owned(project_id, user.id)
        snapshot = await uow.context.snapshot(project_id, items)
        await uow.commit()
        return {"id": snapshot.id, "snapshot_hash": snapshot.snapshot_hash, "item_count": len(items)}
