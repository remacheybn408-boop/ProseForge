from __future__ import annotations

import os
import asyncio

from celery import Celery


celery = Celery(
    "proseforge",
    broker=os.getenv("PROSEFORGE_REDIS_URL", "redis://redis:6379/0"),
    backend=os.getenv("PROSEFORGE_REDIS_URL", "redis://redis:6379/0"),
)
celery.conf.update(
    task_track_started=True,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "sync-provider-model-catalog-daily": {
            "task": "proseforge.providers.sync_all_models",
            "schedule": 24 * 60 * 60,
        },
        "recover-expired-workflows": {
            "task": "proseforge.workflows.recover_expired",
            "schedule": 60.0,
        },
    },
)


@celery.task(name="proseforge.healthcheck")
def healthcheck() -> str:
    return "ok"


@celery.task(name="proseforge.providers.sync_all_models", bind=True, max_retries=0)
def sync_all_provider_models(self) -> dict[str, int]:
    del self
    return asyncio.run(_sync_all_provider_models())


@celery.task(name="proseforge.workflows.recover_expired", bind=True, max_retries=0)
def recover_expired_workflows(self) -> int:
    del self
    return asyncio.run(_recover_expired_workflows())


async def _recover_expired_workflows() -> int:
    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
    from proseforge.settings import get_settings

    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings)
    try:
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            recovered = await uow.workflows.recover_expired()
            await uow.commit()
            return recovered
    finally:
        await engine.dispose()


async def _sync_all_provider_models() -> dict[str, int]:
    import base64
    import binascii
    import hashlib
    import json

    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
    from proseforge.infrastructure.security.credential_cipher import CredentialCipher
    from proseforge.providers.factory import build_provider
    from proseforge.settings import get_settings

    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings)
    synced = 0
    failed = 0
    try:
        raw_key = settings.master_key.get_secret_value()
        try:
            key = base64.b64decode(raw_key, validate=True)
        except (ValueError, binascii.Error):
            key = b""
        if len(key) != 32:
            key = hashlib.sha256(raw_key.encode()).digest()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            for credential in await uow.credentials.list_all():
                try:
                    associated = f"{credential.user_id}:{credential.provider}:{credential.id}".encode()
                    secret = json.loads(CredentialCipher(key).decrypt(base64.b64decode(credential.encrypted_payload), associated_data=associated))
                    provider = build_provider(credential.provider, secret["api_key"], secret.get("base_url"))
                    models = await provider.list_models()
                    await uow.model_catalog.upsert(models)
                    await uow.model_catalog.mark_unavailable(credential.provider, {model.model_id for model in models})
                    synced += 1
                except Exception:
                    failed += 1
            await uow.commit()
    finally:
        await engine.dispose()
    return {"synced": synced, "failed": failed}


@celery.task(name="proseforge.chat.generate", bind=True, autoretry_for=(), max_retries=0)
def generate_chat(self, payload: dict[str, object]) -> str:
    """Run one durable chat generation task in the worker process."""
    del self
    return asyncio.run(_generate_chat(payload))


async def _generate_chat(payload: dict[str, object]) -> str:
    import base64
    import binascii
    import hashlib
    import json

    from proseforge.application.conversations.generate_reply import GenerateReply
    from proseforge.domain.ports.model_provider import GenerationRequest
    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
    from proseforge.infrastructure.events.database import DatabaseEventStream
    from proseforge.infrastructure.security.credential_cipher import CredentialCipher
    from proseforge.providers.factory import build_provider
    from proseforge.settings import get_settings

    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings)
    try:
        message_id = str(payload["message_id"])
        user_id = str(payload.get("user_id", ""))
        provider_id = str(payload.get("provider", "openai"))
        model = str(payload.get("model", "gpt-4.1-mini"))
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            credential = await uow.credentials.get_for_user(user_id, provider_id)
            message = await uow.conversations.get_message(message_id)
            visible = await uow.conversations.list_visible_messages(message.branch_id) if message else []
            user_message = next((item for item in reversed(visible) if item.role == "user"), None)
            if credential is None or user_message is None:
                if message:
                    await uow.conversations.set_message_status(message_id, "PARTIAL")
                    await uow.commit()
                return "provider-not-configured"
            try:
                raw = base64.b64decode(settings.master_key.get_secret_value(), validate=True)
            except (ValueError, binascii.Error):
                raw = b""
            if len(raw) != 32:
                raw = hashlib.sha256(settings.master_key.get_secret_value().encode()).digest()
            associated = f"{user_id}:{provider_id}:{credential.id}".encode()
            secret = json.loads(CredentialCipher(raw).decrypt(base64.b64decode(credential.encrypted_payload), associated_data=associated))
        base_url = secret.get("base_url")
        try:
            provider = build_provider(provider_id, secret["api_key"], base_url=base_url)
        except KeyError:
            return "provider-not-supported"
        input_blocks = [{"role": "user", "text": user_message.content}]
        if message is not None and message.status == "PARTIAL" and message.content:
            input_blocks.append({"role": "assistant", "text": message.content})
            input_blocks.append({"role": "user", "text": "Continue from the saved partial response without repeating existing text."})
        request = GenerationRequest(model=model, system_blocks=(), input_blocks=tuple(input_blocks))
        await GenerateReply(lambda: SqlAlchemyUnitOfWork(session_factory), provider, DatabaseEventStream(session_factory)).execute(message_id=message_id, request=request)
        return "completed"
    finally:
        await engine.dispose()
