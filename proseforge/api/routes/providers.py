from __future__ import annotations

from typing import Annotated

import base64
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user
from proseforge.api.dependencies import unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.infrastructure.security.credential_cipher import CredentialCipher
from proseforge.providers.factory import build_provider

router = APIRouter(prefix="/api/v1", tags=["providers"])


class CustomModelRequest(BaseModel):
    provider: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=200)
    display_name: str | None = None
    capabilities: dict[str, object] = Field(default_factory=dict)


@router.get("/providers")
async def list_providers(request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> list[dict[str, object]]:
    del user
    return [{"id": provider_id, "status": "configured"} for provider_id in request.app.state.provider_registry.ids()]


@router.get("/models")
async def list_models(
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
    provider: str | None = None,
    q: str | None = None,
    available_only: bool = True,
) -> list[dict[str, object]]:
    del request, user
    async with uow:
        return [{"provider": model.provider, "model_id": model.model_id, "display_name": model.display_name, "capabilities": model.capabilities, "context_window": model.context_window, "max_output_tokens": model.max_output_tokens} for model in await uow.model_catalog.list(provider, q, available_only)]


@router.post("/models", status_code=201)
async def add_custom_model(
    payload: CustomModelRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    del user
    capabilities = {**payload.capabilities, "manual": True, "availability": "available"}
    from proseforge.domain.ports.model_provider import ProviderModel
    model = ProviderModel(payload.provider, payload.model_id, payload.display_name or payload.model_id, capabilities)
    async with uow:
        await uow.model_catalog.upsert([model])
        await uow.commit()
        return {"provider": model.provider, "model_id": model.model_id, "display_name": model.display_name, "capabilities": capabilities}


@router.post("/providers/{provider_id}/sync-models")
async def sync_models(
    provider_id: str,
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        credential = await uow.credentials.get_for_user(user.id, provider_id)
        if credential is None:
            raise HTTPException(status_code=400, detail="provider credentials are not configured")
        raw_key = request.app.state.settings.master_key.get_secret_value()
        try:
            key = base64.b64decode(raw_key, validate=True)
        except Exception:
            key = hashlib.sha256(raw_key.encode()).digest()
        associated = f"{user.id}:{provider_id}:{credential.id}".encode()
        try:
            payload = json.loads(CredentialCipher(key).decrypt(base64.b64decode(credential.encrypted_payload), associated_data=associated))
            provider = build_provider(provider_id, payload["api_key"], payload.get("base_url"))
            models = await provider.list_models()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"provider not registered: {provider_id}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"provider model discovery failed: {type(exc).__name__}") from exc
        await uow.model_catalog.upsert([model for model in models])
        await uow.model_catalog.mark_unavailable(provider_id, {model.model_id for model in models})
        await uow.commit()
        return {"provider": provider_id, "count": len(models), "models": [model.model_id for model in models]}


@router.post("/providers/{provider_id}/probe")
async def probe_provider(
    provider_id: str,
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        credential = await uow.credentials.get_for_user(user.id, provider_id)
        if credential is None:
            raise HTTPException(status_code=400, detail="provider credentials are not configured")
        raw_key = request.app.state.settings.master_key.get_secret_value()
        try:
            key = base64.b64decode(raw_key, validate=True)
        except Exception:
            key = hashlib.sha256(raw_key.encode()).digest()
        associated = f"{user.id}:{provider_id}:{credential.id}".encode()
        try:
            payload = json.loads(CredentialCipher(key).decrypt(base64.b64decode(credential.encrypted_payload), associated_data=associated))
            provider = build_provider(provider_id, payload["api_key"], payload.get("base_url"))
            result = await provider.validate_credentials()
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"provider not registered: {provider_id}") from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"provider probe failed: {type(exc).__name__}") from exc
        return {"provider": provider_id, **result}
