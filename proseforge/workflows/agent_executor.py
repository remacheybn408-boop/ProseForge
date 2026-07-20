"""V3 agent run 持久执行器（蓝图 V3-004/005）。

把一个持久化的 V3 task graph 按 checkpoint 逐批执行到终态：
- 每次调用先一次性恢复滞留 RUNNING 任务（task.recovered），循环顶与
  提交前都尊重 PAUSED/CANCELLED（任务重置回 PENDING）；
- 依赖就绪（depends_on 全部 SUCCEEDED）的任务按 ``MAX_PARALLEL_TASKS``
  有界认领，经 ``bounded_parallel`` 信号量并行执行；
- 模型调用发生在任何数据库事务之外；每个任务在自己的短事务里提交
  Artifact + 事件 + 实测 usage 结算 + run.checkpoint_id（提交阶段由
  commit_lock 串行，保证 (run_id, sequence) 唯一且单调递增）；
- 有任务 FAILED 且无 PENDING 可重试时 run 以 FAILED 收场（不误报 COMPLETED）；
- Chief Editor 产出仍走 V2 RevisionProposal（后续 workstream 以
  register_role 注册的真正 chief handler 替换，见 application/agents/role_handlers.py）。
"""

from __future__ import annotations

from functools import partial

from proseforge.application.agents.parallel import bounded_parallel
from proseforge.application.agents.role_handlers import RoleResult, allowed_artifact_types, handler_for, validate_artifact_payload

MAX_PARALLEL_TASKS = 16  # server profile（蓝图 V3-004：native 4 / server 16）
EXECUTOR_VERSION = "v3-exec-1"
TASK_LEASE_TTL_SECONDS = 60
DEFAULT_MAX_ATTEMPTS = 3  # AgentTaskModel 尚无 max_attempts 列，沿用 AgentTaskSpec 默认


def validate_role_result(role: str, result: RoleResult) -> str | None:
    """服务端校验：先查角色 allowlist（domain/agents/roles.py），再查类型 schema。"""
    if result.artifact_type not in allowed_artifact_types(role):
        return f"artifact type {result.artifact_type} not allowed for role {role}"
    return validate_artifact_payload(result.artifact_type, result.payload)


async def execute_run(payload: dict[str, object]) -> str:
    import asyncio
    import base64
    import binascii
    import hashlib
    import json
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import select

    from proseforge.domain.common.ids import new_id
    from proseforge.infrastructure.database.models.agents import AgentArtifactModel, AgentEventModel, AgentRunModel, AgentTaskModel
    from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
    from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
    from proseforge.infrastructure.security.credential_cipher import CredentialCipher
    from proseforge.providers.factory import build_provider
    from proseforge.settings import get_settings

    settings = get_settings()
    engine, session_factory = create_engine_and_sessionmaker(settings)
    run_id, user_id = str(payload["run_id"]), str(payload.get("user_id", ""))
    provider_id = str(payload.get("provider", "openai"))
    model_id = str(payload.get("model", "gpt-4.1-mini"))
    recover_stale = True
    provider = None
    secret: dict[str, object] = {}
    commit_lock = asyncio.Lock()  # 提交串行化：事件 sequence 与 checkpoint 写不竞争
    # 迁移 workstream 补上 lease_expires_at 列后自动启用 TTL；当前认领语义
    # 仍是 status=RUNNING + checkpoint_id（lease_owner 列已存在，仅作观测）。
    lease_ttl_supported = hasattr(AgentTaskModel, "lease_expires_at")

    async def add_event(uow, run, event_type: str, data: dict[str, object] | None = None) -> None:
        # run 行锁串行分配 sequence（并行提交/重复投递下不撞 uq_agent_events_run_sequence）
        locked = await uow.session.scalar(
            select(AgentRunModel).where(AgentRunModel.id == run.id).with_for_update().execution_options(populate_existing=True)
        )
        sequence = int(locked.event_cursor) + 1
        uow.session.add(AgentEventModel(id=new_id(), run_id=locked.id, sequence=sequence, event_type=event_type, payload=json.dumps(data or {}, sort_keys=True)))
        locked.event_cursor = sequence
        locked.updated_at = datetime.now(UTC)

    async def fail_run(uow, run, status: str, reason: str, event_type: str = "run.failed", data: dict[str, object] | None = None) -> None:
        run.status = status
        run.terminal_reason = reason
        await add_event(uow, run, event_type, data or {"reason": reason})

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
                        task.lease_owner = None
                        await add_event(uow, run, "task.recovered", {"task_id": task.id, "task_key": task.task_key})
                    recover_stale = False
                    if recovered:
                        await uow.commit()
                        continue
                succeeded = {task.task_key for task in tasks if task.status == "SUCCEEDED"}
                pending = [task for task in tasks if task.status == "PENDING"]
                if not pending:
                    failed = [task for task in tasks if task.status == "FAILED"]
                    if failed:
                        # 有任务 FAILED 且无 PENDING 可重试：run 必须 FAILED 收场
                        await fail_run(uow, run, "FAILED", "task(s) failed without retry", data={"reason": "task(s) failed without retry", "failed_tasks": [task.task_key for task in failed]})
                        await uow.commit()
                        return "failed"
                    run.status = "COMPLETED"
                    await add_event(uow, run, "run.completed")
                    await uow.commit()
                    return "completed"
                ready = [task for task in pending if set(json.loads(task.depends_on)) <= succeeded]
                if not ready:
                    await fail_run(uow, run, "FAILED", "task dependency could not be satisfied")
                    await uow.commit()
                    return "failed"
                claimed: list[AgentTaskModel] = []
                for task in ready:
                    if len(claimed) >= MAX_PARALLEL_TASKS:
                        break
                    if run.budget_used + task.token_budget > run.budget_limit:
                        # 起前估算（token_budget）超额：durable BUDGET_EXHAUSTED
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
                    task.lease_owner = f"celery:{run.id}:{task.task_key}"
                    if lease_ttl_supported:
                        task.lease_expires_at = datetime.now(UTC) + timedelta(seconds=TASK_LEASE_TTL_SECONDS)
                    await add_event(uow, run, "task.started", {"task_id": task.id, "task_key": task.task_key, "role": task.role})
                    await add_event(uow, run, "task.lease_acquired", {"task_id": task.id, "task_key": task.task_key, "lease_owner": task.lease_owner, "lease_ttl_seconds": TASK_LEASE_TTL_SECONDS})
                    claimed.append(task)
                if claimed and provider is None:
                    # 解析 run owner 凭据（与 generate_novel 同一解密流程）；模型调用仍在事务外
                    credential = await uow.credentials.get_for_user(user_id, provider_id)
                    if credential is None:
                        for task in claimed:
                            task.status = "PENDING"
                            task.lease_owner = None
                        await fail_run(uow, run, "FAILED", "provider-or-project-not-configured")
                        await uow.commit()
                        return "provider-or-project-not-configured"
                    associated = f"{user_id}:{provider_id}:{credential.id}".encode()
                    try:
                        raw_key = base64.b64decode(settings.master_key.get_secret_value(), validate=True)
                    except (ValueError, binascii.Error):
                        raw_key = b""
                    if len(raw_key) != 32:
                        raw_key = hashlib.sha256(settings.master_key.get_secret_value().encode()).digest()
                    secret = json.loads(CredentialCipher(raw_key).decrypt(base64.b64decode(credential.encrypted_payload), associated_data=associated))
                task_key_by_id = {task.id: task.task_key for task in tasks}
                artifacts_snapshot = [
                    {"id": row.id, "task_key": task_key_by_id.get(row.task_id, ""), "artifact_type": row.artifact_type, "preview": row.preview}
                    for row in await uow.session.scalars(select(AgentArtifactModel).where(AgentArtifactModel.run_id == run.id))
                ]
                claimed_snapshot = [{"id": task.id, "task_key": task.task_key, "role": task.role} for task in claimed]
                run_snapshot = {"id": run.id, "goal_hash": run.goal_hash, "graph_revision": run.graph_revision, "project_id": run.project_id, "chapter_id": run.chapter_id, "base_version_id": run.base_version_id}
                await uow.commit()

            if provider is None:
                try:
                    provider = build_provider(provider_id, str(secret["api_key"]), secret.get("base_url"))
                except KeyError:
                    async with SqlAlchemyUnitOfWork(session_factory) as uow:
                        run = await uow.session.scalar(select(AgentRunModel).where(AgentRunModel.id == run_id, AgentRunModel.user_id == user_id))
                        if run is None:
                            return "run-not-found"
                        for info in claimed_snapshot:
                            task = await uow.session.get(AgentTaskModel, info["id"])
                            if task is not None and task.status == "RUNNING":
                                task.status = "PENDING"
                                task.lease_owner = None
                        await fail_run(uow, run, "FAILED", "provider-not-supported")
                        await uow.commit()
                    return "provider-not-supported"

            async def run_claimed(info: dict[str, object]) -> str:
                context = {
                    "run": run_snapshot,
                    "task": info,
                    "provider": provider,
                    "provider_id": provider_id,
                    "model": model_id,
                    "uow_factory": lambda: SqlAlchemyUnitOfWork(session_factory),
                    "artifacts": artifacts_snapshot,
                }
                result: RoleResult | None = None
                error: Exception | None = None
                try:
                    # 模型调用在任何数据库事务之外
                    result = await handler_for(str(info["role"]))(context)
                except Exception as exc:  # 解析/模型错误按 malformed_json 语义重试或失败
                    error = exc
                async with commit_lock:
                    async with SqlAlchemyUnitOfWork(session_factory) as uow:
                        run = await uow.session.scalar(select(AgentRunModel).where(AgentRunModel.id == run_id, AgentRunModel.user_id == user_id))
                        task = await uow.session.get(AgentTaskModel, info["id"])
                        if run is None or task is None:
                            return "run-not-found"
                        if run.status != "RUNNING":
                            # PAUSED/CANCELLED（或异常终态）：退回 PENDING，不留半成品
                            task.status = "PENDING"
                            task.lease_owner = None
                            await uow.commit()
                            return run.status.lower()
                        if error is not None:
                            task.last_error = f"{type(error).__name__}: {str(error)[:200]}"
                            task.lease_owner = None
                            if task.attempts < DEFAULT_MAX_ATTEMPTS:
                                task.status = "PENDING"
                                await add_event(uow, run, "task.failed", {"task_id": task.id, "task_key": task.task_key, "error": type(error).__name__, "retry": True})
                            else:
                                task.status = "FAILED"
                                await add_event(uow, run, "task.failed", {"task_id": task.id, "task_key": task.task_key, "error": type(error).__name__, "retry": False})
                            await uow.commit()
                            return "failed"
                        validation_error = validate_role_result(task.role, result)
                        if validation_error is not None:
                            # 服务端校验失败：任务 FAILED，run 继续其余任务
                            task.status = "FAILED"
                            task.last_error = validation_error
                            task.lease_owner = None
                            await add_event(uow, run, "task.failed", {"task_id": task.id, "task_key": task.task_key, "error": validation_error, "retry": False})
                            await uow.commit()
                            return "failed"
                        raw = json.dumps(result.payload, ensure_ascii=False, sort_keys=True).encode()
                        artifact = AgentArtifactModel(
                            id=new_id(), run_id=run.id, task_id=task.id, artifact_type=result.artifact_type,
                            sha256=hashlib.sha256(raw).hexdigest(),
                            provenance=json.dumps({"task_id": task.id, "task_key": task.task_key, "role": task.role, "model": model_id, "provider": provider_id}, sort_keys=True),
                            preview=f"{task.role} {result.artifact_type}"[:80],
                            payload=json.dumps(result.payload, ensure_ascii=False, sort_keys=True),
                        )
                        uow.session.add(artifact)
                        task.status = "SUCCEEDED"
                        task.checkpoint_id = f"{run.id}:{task.task_key}:committed"
                        task.lease_owner = None
                        run.budget_used += result.used_tokens  # 实测 usage 结算（替代申报 token_budget 记账）
                        await add_event(uow, run, "task.usage", {"task_id": task.id, "task_key": task.task_key, "input_tokens": result.input_tokens, "output_tokens": result.output_tokens, "total_tokens": result.used_tokens})
                        for extra in result.extra_events:
                            await add_event(uow, run, str(extra.get("event", "task.event")), {key: value for key, value in extra.items() if key != "event"})
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
                        crash_after_artifact_commit = run.fault_mode == "crash_after_artifact_commit"
                        if crash_after_artifact_commit:
                            # 与 artifact/checkpoint 同一事务清开关：redelivery 观察到
                            # SUCCEEDED，只补 run.completed，不再产第二个 artifact。
                            run.fault_mode = None
                        done = sorted(await uow.session.scalars(select(AgentTaskModel.task_key).where(AgentTaskModel.run_id == run.id, AgentTaskModel.status == "SUCCEEDED")))
                        run.checkpoint_id = f"graph:{run.graph_revision}|done:{','.join(done)}|cursor:{run.event_cursor}|exec:{EXECUTOR_VERSION}"
                        await uow.commit()
                        if crash_after_artifact_commit:
                            import os
                            os._exit(137)
                        return "succeeded"

            await bounded_parallel([partial(run_claimed, info) for info in claimed_snapshot], MAX_PARALLEL_TASKS)
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
