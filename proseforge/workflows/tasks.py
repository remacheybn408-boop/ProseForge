"""任务 handler 实现（celery-free，V15-004）。

5 个持久任务的实际执行体，统一签名为
``async handler(payload: dict[str, object]) -> object``。
模块级不 import celery——native profile 的 LocalTaskQueue 直接复用
HANDLERS；celery_app.py 只做薄封装（asyncio.run + celery.task 注册）。
重型依赖全部在函数体内惰性 import。
"""

from __future__ import annotations

from typing import Awaitable, Callable

TaskHandler = Callable[[dict[str, object]], Awaitable[object]]


def should_abort_workflow(status: str) -> bool:
    return status == "CANCELLED"


async def generate_novel(payload: dict[str, object]) -> str:
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
    from proseforge.context_engine.compiler import compile_context
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
            context_items = [item for item in await uow.context.list_owned(run.project_id, owner_id) if not item.excluded]
            context_blocks = [{"id": item.id, "source_type": item.source_type, "content": item.content, "pinned": item.pinned, "priority": item.priority} for item in context_items]
            snapshot = await uow.context.snapshot(run.project_id, context_items)
            compiled_context = compile_context(snapshot.id, context_blocks, input_budget=8000)
            context_text = "\n".join(str(block.get("content", "")) for block in compiled_context.blocks)
            await uow.workflows.checkpoint(run, lease_owner, f"PREPARING_CONTEXT_{snapshot.snapshot_hash}")
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
            content, rewrite_rounds, _review = await run_writer_editor_loop(provider, writer_model=model_id, editor_model=str(payload.get("editor_model", model_id)), project_title=project.title, chapter_title=chapter.title, context_text=context_text)
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


async def healthcheck(payload: dict[str, object]) -> str:
    del payload
    return "ok"


async def sync_all_models(payload: dict[str, object]) -> dict[str, int]:
    import base64
    import binascii
    import hashlib
    import json

    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
    from proseforge.infrastructure.security.credential_cipher import CredentialCipher
    from proseforge.providers.factory import build_provider
    from proseforge.settings import get_settings

    del payload
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


async def recover_expired(payload: dict[str, object]) -> int:
    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
    from proseforge.settings import get_settings

    del payload
    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings)
    try:
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            recovered = await uow.workflows.recover_expired()
            await uow.commit()
            return recovered
    finally:
        await engine.dispose()


async def execute_agent_run(payload: dict[str, object]) -> str:
    """Execute a persisted V3 graph one checkpoint at a time.

    The worker owns task transitions and artifact writes; it never writes a
    ChapterVersion.  Chief Editor output is routed through V2 proposals.
    """
    import hashlib
    import json
    from datetime import UTC, datetime
    from sqlalchemy import select, func
    from proseforge.domain.common.ids import new_id
    from proseforge.infrastructure.database.models.agents import AgentArtifactModel, AgentEventModel, AgentRunModel, AgentTaskModel
    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
    from proseforge.settings import get_settings

    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings)
    run_id, user_id = str(payload["run_id"]), str(payload.get("user_id", ""))
    recover_stale = True

    async def add_event(uow, run, event_type: str, data: dict[str, object] | None = None) -> None:
        sequence = int(await uow.session.scalar(select(func.max(AgentEventModel.sequence)).where(AgentEventModel.run_id == run.id)) or 0) + 1
        uow.session.add(AgentEventModel(id=new_id(), run_id=run.id, sequence=sequence, event_type=event_type, payload=json.dumps(data or {}, sort_keys=True)))
        run.event_cursor = sequence
        run.updated_at = datetime.now(UTC)

    try:
        while True:
            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                run = await uow.session.scalar(select(AgentRunModel).where(AgentRunModel.id == run_id, AgentRunModel.user_id == user_id))
                if run is None:
                    return "run-not-found"
                if run.status in {"CANCELLED", "PAUSED"}:
                    return run.status.lower()
                if run.fault_mode == "provider_timeout":
                    raise TimeoutError("injected provider timeout")
                if run.fault_mode == "malformed_json":
                    json.loads("{malformed agent output")
                if run.fault_mode == "budget_exhaustion":
                    run.status = "BUDGET_EXHAUSTED"
                    run.terminal_reason = "injected budget exhaustion"
                    await add_event(uow, run, "run.budget_exhausted", {"injected": True})
                    await uow.commit()
                    return "budget-exhausted"
                if run.status == "PENDING":
                    run.status = "RUNNING"
                    await add_event(uow, run, "run.started")
                tasks = list(await uow.session.scalars(select(AgentTaskModel).where(AgentTaskModel.run_id == run.id).order_by(AgentTaskModel.id)))
                if recover_stale:
                    recovered = [task for task in tasks if task.status == "RUNNING"]
                    for task in recovered:
                        task.status = "PENDING"
                        task.last_error = "worker restarted before checkpoint commit"
                        await add_event(uow, run, "task.recovered", {"task_id": task.id, "task_key": task.task_key})
                    recover_stale = False
                    if recovered:
                        await uow.commit()
                        continue
                succeeded = {task.task_key for task in tasks if task.status == "SUCCEEDED"}
                pending = [task for task in tasks if task.status == "PENDING"]
                if not pending:
                    run.status = "COMPLETED"
                    await add_event(uow, run, "run.completed")
                    await uow.commit()
                    return "completed"
                task = next((candidate for candidate in pending if set(json.loads(candidate.depends_on)) <= succeeded), None)
                if task is None:
                    run.status = "FAILED"
                    run.terminal_reason = "task dependency could not be satisfied"
                    await add_event(uow, run, "run.failed", {"reason": run.terminal_reason})
                    await uow.commit()
                    return "failed"
                if run.budget_used + task.token_budget > run.budget_limit:
                    task.status = "FAILED"
                    task.last_error = "budget exhausted"
                    run.status = "BUDGET_EXHAUSTED"
                    run.terminal_reason = "task token budget exceeds remaining run budget"
                    await add_event(uow, run, "run.budget_exhausted", {"task_id": task.id, "required": task.token_budget, "remaining": run.budget_limit - run.budget_used})
                    await uow.commit()
                    return "budget-exhausted"
                task.status = "RUNNING"
                task.attempts += 1
                task.checkpoint_id = f"{run.id}:{task.task_key}:{task.attempts}"
                await add_event(uow, run, "task.started", {"task_id": task.id, "task_key": task.task_key, "role": task.role})
                await uow.commit()

            async with SqlAlchemyUnitOfWork(session_factory) as uow:
                run = await uow.session.scalar(select(AgentRunModel).where(AgentRunModel.id == run_id, AgentRunModel.user_id == user_id))
                task = await uow.session.scalar(select(AgentTaskModel).where(AgentTaskModel.run_id == run_id, AgentTaskModel.status == "RUNNING"))
                if run is None or task is None:
                    return "run-not-found"
                if run.status in {"CANCELLED", "PAUSED"}:
                    task.status = "PENDING"
                    await uow.commit()
                    return run.status.lower()
                candidate = {"task_key": task.task_key, "role": task.role, "goal_hash": run.goal_hash}
                raw = json.dumps(candidate, sort_keys=True).encode()
                artifact = AgentArtifactModel(
                    id=new_id(), run_id=run.id, task_id=task.id, artifact_type="candidate",
                    sha256=hashlib.sha256(raw).hexdigest(), provenance=json.dumps({"task_id": task.id, "role": task.role}, sort_keys=True),
                    preview=f"{task.role} candidate", payload=json.dumps(candidate, sort_keys=True),
                )
                uow.session.add(artifact)
                task.status = "SUCCEEDED"
                task.checkpoint_id = f"{run.id}:{task.task_key}:committed"
                run.budget_used += task.token_budget
                await add_event(uow, run, "artifact.committed", {"artifact_id": artifact.id, "task_id": task.id, "sha256": artifact.sha256})
                await add_event(uow, run, "task.succeeded", {"task_id": task.id, "task_key": task.task_key})
                if task.role == "chief_editor" and run.chapter_id and run.base_version_id:
                    base = await uow.chapters.get_version_owned(run.chapter_id, run.base_version_id, user_id)
                    if base is None:
                        raise ValueError("chief editor base version not found")
                    proposal = await uow.revisions.create(
                        chapter_id=run.chapter_id, base_version_id=base.id, before=base.content,
                        after=base.content + "\n\n" + f"[Agent candidate: {task.task_key}]",
                        rationale="Chief Editor candidate produced by the reviewed V3 run.",
                    )
                    run.proposal_id = proposal.id
                    await add_event(uow, run, "proposal.created", {"proposal_id": proposal.id})
                await uow.commit()
    except Exception as exc:
        async with SqlAlchemyUnitOfWork(session_factory) as uow:
            run = await uow.session.scalar(select(AgentRunModel).where(AgentRunModel.id == run_id, AgentRunModel.user_id == user_id))
            if run is not None:
                run.status = "FAILED"
                run.terminal_reason = type(exc).__name__
                await add_event(uow, run, "run.failed", {"reason": type(exc).__name__})
                await uow.commit()
        raise
    finally:
        await engine.dispose()


async def generate_chat(payload: dict[str, object]) -> str:
    """Run one durable chat generation task in the worker process."""
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


HANDLERS: dict[str, TaskHandler] = {
    "proseforge.workflows.generate_novel": generate_novel,
    "proseforge.chat.generate": generate_chat,
    "proseforge.providers.sync_all_models": sync_all_models,
    "proseforge.workflows.recover_expired": recover_expired,
    "proseforge.healthcheck": healthcheck,
    "proseforge.agents.execute_run": execute_agent_run,
}
