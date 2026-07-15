from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from proseforge.api.dependencies import current_user
from proseforge.application.auth.service import AuthUser

router = APIRouter(prefix="/api/v1", tags=["providers"])


@router.get("/providers")
async def list_providers(request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> list[dict[str, object]]:
    del user
    return [{"id": provider_id, "status": "configured"} for provider_id in request.app.state.provider_registry.ids()]


@router.get("/models")
async def list_models(request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> list[dict[str, object]]:
    del user
    return [model.__dict__ for model in request.app.state.model_catalog.values()]
