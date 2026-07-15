from __future__ import annotations

from typing import Annotated

import base64
import hashlib
import json

from fastapi import APIRouter, Depends, HTTPException, Request

from proseforge.api.dependencies import current_user
from proseforge.api.dependencies import unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.infrastructure.security.credential_cipher import CredentialCipher
from proseforge.providers.factory import build_provider

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
        await uow.model_catalog.upsert(models)
        await uow.commit()
        return {"provider": provider_id, "count": len(models), "models": [model.model_id for model in models]}
