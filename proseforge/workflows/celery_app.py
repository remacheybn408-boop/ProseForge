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
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
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


def should_abort_workflow(status: str) -> bool:
    return status == "CANCELLED"


@celery.task(name="proseforge.workflows.generate_novel", bind=True, max_retries=0)
def generate_novel_workflow(self, payload: dict[str, object]) -> str:
    del self
    return asyncio.run(_generate_novel_workflow(payload))


async def _generate_novel_workflow(payload: dict[str, object]) -> str:
    import base64
    import binascii
    import hashlib
    import json

    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
    from proseforge.infrastructure.security.credential_cipher import CredentialCipher
    from proseforge.providers.factory import build_provider
    from proseforge.settings import get_settings
    from proseforge.domain.workflow.budget import budget_blocked
    from proseforge.workflows.novel_generation import run_writer_editor_loop

    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings)
    workflow_id = str(payload["workflow_id"])
    owner_id = str(payload.get("user_id", ""))
    provider_id = str(payload.get("provider", "openai"))
    model_id = str(payload.get("model", "gpt-4.1-mini"))
    lease_owner = f"celery:{workflow_id}"
    try:
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            run = await uow.workflows.get_owned(workflow_id, owner_id)
            if run is None:
                return "workflow-not-found"
            if should_abort_workflow(run.status):
                return "cancelled"
            if run.status == "QUEUED":
                await uow.workflows.transition(run, "RUNNING")
            if not await uow.workflows.acquire_lease(run, lease_owner):
                return "lease-unavailable"
            credential = await uow.credentials.get_for_user(owner_id, provider_id)
            project = await uow.projects.get_by_id(owner_id, run.project_id)
            chapters = await uow.chapters.list_owned(run.project_id, owner_id)
            if credential is None or project is None:
                await uow.workflows.transition(run, "FAILED")
                await uow.commit()
                return "provider-or-project-not-configured"
            associated = f"{owner_id}:{provider_id}:{credential.id}".encode()
            try:
                raw = base64.b64decode(settings.master_key.get_secret_value(), validate=True)
            except (ValueError, binascii.Error):
                raw = b""
            if len(raw) != 32:
                raw = hashlib.sha256(settings.master_key.get_secret_value().encode()).digest()
            secret = json.loads(CredentialCipher(raw).decrypt(base64.b64decode(credential.encrypted_payload), associated_data=associated))
            provider = build_provider(provider_id, secret["api_key"], secret.get("base_url"))
            requested = [int(item) for item in payload.get("chapter_numbers", [])]
            targets = [chapter for chapter in chapters if not requested or chapter.chapter_no in requested]
            if not targets:
                await uow.workflows.transition(run, "FAILED")
                await uow.commit()
                return "no-chapters"
            # Persist the lease/checkpoint before leaving the transaction.
            await uow.workflows.checkpoint(run, lease_owner, "PREPARING")
            await uow.commit()

        for chapter in targets:
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                run = await uow.workflows.get_owned(workflow_id, owner_id)
                if run is None:
                    return "workflow-not-found"
                if should_abort_workflow(run.status):
                    return "cancelled"
                if run.status == "PAUSED":
                    return "paused"
                if budget_blocked(used_tokens=int(getattr(run, "used_tokens", 0) or 0), token_limit=int(getattr(run, "token_limit", 0) or 0), estimated_next_tokens=1, estimated_cost=float(run.estimated_cost or 0), cost_limit=float(run.cost_limit or 0), estimated_next_cost=None):
                    await uow.workflows.transition(run, "BUDGET_BLOCKED")
                    await uow.commit()
                    return "budget-blocked"
                await uow.workflows.heartbeat(run, lease_owner)
                await uow.workflows.checkpoint(run, lease_owner, f"CHAPTER_{chapter.chapter_no}_DRAFTING")
                await uow.commit()
            content, rewrite_rounds, _review = await run_writer_editor_loop(provider, writer_model=model_id, editor_model=str(payload.get("editor_model", model_id)), project_title=project.title, chapter_title=chapter.title)
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                run = await uow.workflows.get_owned(workflow_id, owner_id)
                if run is None:
                    return "workflow-not-found"
                if should_abort_workflow(run.status):
                    return "cancelled"
                if run.status == "PAUSED":
                    return "paused"
                version = await uow.chapters.append_version(chapter_id=chapter.id, content=content)
                await uow.chapters.set_active_version(chapter.id, version.id)
                await uow.workflows.checkpoint(run, lease_owner, f"CHAPTER_{chapter.chapter_no}_COMMITTED_REWRITES_{rewrite_rounds}")
                await uow.commit()
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            run = await uow.workflows.get_owned(workflow_id, owner_id)
            if run is not None and should_abort_workflow(run.status):
                return "cancelled"
            if run is not None and run.status == "RUNNING":
                await uow.workflows.transition(run, "COMPLETED")
                await uow.commit()
        return "completed"
    except Exception as error:
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            run = await uow.workflows.get_owned(workflow_id, owner_id)
            if run is not None and run.status in {"RUNNING", "RETRYING", "RECOVERING"}:
                run.last_error = type(error).__name__
                await uow.workflows.transition(run, "FAILED")
                await uow.commit()
        raise
    finally:
        await engine.dispose()


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
    from proseforge.application.conversations.terminal_state import terminal_message_status
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
                    await uow.conversations.set_message_status(message_id, terminal_message_status(len(message.content)))
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
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                message = await uow.conversations.get_message(message_id)
                if message:
                    await uow.conversations.set_message_status(message_id, terminal_message_status(len(message.content)))
                    await uow.commit()
            return "provider-not-supported"
        input_blocks = [{"role": "user", "text": user_message.content}]
        if message is not None and message.status == "PARTIAL" and message.content:
            input_blocks.append({"role": "assistant", "text": message.content})
            input_blocks.append({"role": "user", "text": "Continue from the saved partial response without repeating existing text."})
        request = GenerationRequest(model=model, system_blocks=(), input_blocks=tuple(input_blocks))
        await GenerateReply(lambda: SqlAlchemyUnitOfWork(session_factory), provider, DatabaseEventStream(session_factory)).execute(message_id=message_id, request=request, user_id=user_id, provider=provider_id, model=model)
        return "completed"
    finally:
        await engine.dispose()
