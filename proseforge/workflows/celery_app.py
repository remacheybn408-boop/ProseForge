from __future__ import annotations

import os
import asyncio

from celery import Celery

from proseforge.workflows.tasks import (
    HANDLERS,
    generate_chat,
    generate_novel,
    healthcheck as run_healthcheck,
    recover_expired,
    should_abort_workflow,  # noqa: F401  re-export：既有调用方从这里 import
    sync_all_models,
)


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


@celery.task(name="proseforge.workflows.generate_novel", bind=True, max_retries=0)
def generate_novel_workflow(self, payload: dict[str, object]) -> str:
    del self
    return asyncio.run(generate_novel(payload))


@celery.task(name="proseforge.healthcheck")
def healthcheck() -> str:
    return asyncio.run(run_healthcheck({}))


@celery.task(name="proseforge.providers.sync_all_models", bind=True, max_retries=0)
def sync_all_provider_models(self, payload: dict[str, object] | None = None) -> dict[str, int]:
    del self
    return asyncio.run(sync_all_models(payload or {}))


@celery.task(name="proseforge.workflows.recover_expired", bind=True, max_retries=0)
def recover_expired_workflows(self) -> int:
    del self
    return asyncio.run(recover_expired({}))


@celery.task(name="proseforge.chat.generate", bind=True, autoretry_for=(), max_retries=0)
def generate_chat_task(self, payload: dict[str, object]) -> str:
    """Run one durable chat generation task in the worker process."""
    del self
    return asyncio.run(generate_chat(payload))


__all__ = ["HANDLERS", "celery", "should_abort_workflow"]
