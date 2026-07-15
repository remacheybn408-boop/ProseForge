from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from proseforge.api.dependencies import current_user
from proseforge.api.dependencies import unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1", tags=["providers"])


@router.get("/providers")
async def list_providers(request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> list[dict[str, object]]:
    del user
    return [{"id": provider_id, "status": "configured"} for provider_id in request.app.state.provider_registry.ids()]


@router.get("/models")
async def list_models(
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> list[dict[str, object]]:
    del request, user
    async with uow:
        return [model.__dict__ for model in await uow.model_catalog.list()]
