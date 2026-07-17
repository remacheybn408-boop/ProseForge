from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.application.models.reasoning_policy import resolve_reasoning
from proseforge.domain.model.capabilities import capabilities_from_model

router = APIRouter(prefix="/api/v2", tags=["model-capabilities"])


class ReasoningValidation(BaseModel):
    provider: str
    model_id: str
    level: str = "auto"
    probe: bool = False


@router.get("/models")
async def models(user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work), provider: str | None = None, capability: str | None = None):
    del user
    async with uow:
        values = await uow.model_catalog.list(provider, None, True)
        return [{"provider": item.provider, "model_id": item.model_id, "capabilities": item.capabilities, "context_window": item.context_window, "max_output_tokens": item.max_output_tokens} for item in values if not capability or item.capabilities.get(capability)]


@router.get("/models/{provider}/{model_id}/capabilities")
async def model_capabilities(provider: str, model_id: str, user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work)):
    del user
    async with uow:
        values = await uow.model_catalog.list(provider, model_id, False)
        if not values:
            raise HTTPException(status_code=404, detail="model not found")
        caps = capabilities_from_model(values[0])
        return {"provider": provider, "model_id": model_id, **caps.__dict__}


@router.post("/model-resolutions/validate")
async def validate_resolution(payload: ReasoningValidation, user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work)):
    del user
    async with uow:
        values = await uow.model_catalog.list(payload.provider, payload.model_id, False)
        if not values:
            raise HTTPException(status_code=404, detail="model not found")
        try:
            caps = capabilities_from_model(values[0])
            policy = resolve_reasoning(payload.level, caps)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"provider": payload.provider, "model_id": payload.model_id, "context_window": caps.context_window, "reasoning": policy, "warnings": policy["warnings"]}
