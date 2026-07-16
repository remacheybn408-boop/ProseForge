from __future__ import annotations

import hashlib
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.context_engine.tokenizer import ConservativeTokenizer
from proseforge.context_engine.budgeting import resolve_context_window

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


def _snapshot_response(snapshot) -> dict[str, object]:
    return {
        "id": snapshot.id,
        "project_id": snapshot.project_id,
        "snapshot_hash": snapshot.snapshot_hash,
        "payload": json.loads(snapshot.payload),
    }


def context_budget(model: object | None, used_tokens: int) -> dict[str, int]:
    context_window = resolve_context_window(model)
    output_reserve = getattr(model, "max_output_tokens", None) if model is not None else None
    if not isinstance(output_reserve, int) or output_reserve < 0:
        capabilities = getattr(model, "capabilities", {}) if model is not None else {}
        output_reserve = capabilities.get("max_output_tokens", 0) if isinstance(capabilities, dict) else 0
    if not isinstance(output_reserve, int) or output_reserve < 0:
        output_reserve = 0
    return {
        "context_window": context_window,
        "used_tokens": used_tokens,
        "system_reserved_tokens": 0,
        "history_tokens": 0,
        "output_reserve_tokens": output_reserve,
        "available_tokens": max(0, context_window - used_tokens - output_reserve),
    }


@router.get("/projects/{project_id}/context")
async def list_context(
    project_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
    profile_id: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    model: str | None = Query(default=None),
) -> dict[str, object]:
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        if profile_id:
            profile = await uow.model_profiles.get_owned(user.id, profile_id)
            if profile is None:
                raise HTTPException(status_code=404, detail="model profile not found")
            profile_config = json.loads(profile.config or "{}")
            provider = provider or profile_config.get("provider")
            model = model or profile_config.get("model")
        catalog_model = None
        if provider and model:
            catalog_model = next(
                (item for item in await uow.model_catalog.list(provider, model, available_only=False) if item.model_id == model),
                None,
            )
        items = await uow.context.list_owned(project_id, user.id)
        tokenizer = ConservativeTokenizer()
        used_tokens = sum(tokenizer.count(item.content) for item in items if not item.excluded)
        budget = context_budget(catalog_model, used_tokens)
        return {"items": [_response(item) for item in items], **budget, "provider": provider, "model": model}


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


@router.get("/context/snapshots/{snapshot_id}")
async def get_context_snapshot(snapshot_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        snapshot = await uow.context.get_snapshot_owned(snapshot_id, user.id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="context snapshot not found")
        return _snapshot_response(snapshot)


@router.post("/context/snapshots/{snapshot_id}/validate")
async def validate_context_snapshot(snapshot_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        snapshot = await uow.context.get_snapshot_owned(snapshot_id, user.id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="context snapshot not found")
        encoded = json.dumps(json.loads(snapshot.payload), ensure_ascii=False, sort_keys=True)
        actual_hash = hashlib.sha256(encoded.encode()).hexdigest()
        return {"id": snapshot.id, "valid": actual_hash == snapshot.snapshot_hash, "snapshot_hash": snapshot.snapshot_hash, "actual_hash": actual_hash}


@router.get("/context/snapshots/{snapshot_id}/download")
async def download_context_snapshot(snapshot_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> Response:
    async with uow:
        snapshot = await uow.context.get_snapshot_owned(snapshot_id, user.id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="context snapshot not found")
        body = json.dumps(_snapshot_response(snapshot), ensure_ascii=False, indent=2)
    return Response(content=body, media_type="application/json", headers={"content-disposition": f'attachment; filename="context-{snapshot_id}.json"'})
