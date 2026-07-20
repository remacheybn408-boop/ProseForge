"""V3 executor（proseforge/workflows/agent_executor.py）宿主可跑测试。

sqlite+aiosqlite 真实落库 + FakeProvider 假模型（无网络、无 PG），
settings/credential 种子模式沿用
tests/integration/workflows/test_generate_novel_context_budget.py。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import re
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from proseforge.domain.common.ids import new_id
from proseforge.domain.ports.model_provider import GenerationEvent
from proseforge.infrastructure.database.base import Base
from proseforge.infrastructure.database.models.agents import AgentArtifactModel, AgentEventModel, AgentRunModel, AgentTaskModel
from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.infrastructure.security.credential_cipher import CredentialCipher
from proseforge.settings import Settings, get_settings
from proseforge.workflows.agent_executor import DEFAULT_MAX_ATTEMPTS, EXECUTOR_VERSION, MAX_PARALLEL_TASKS, execute_run

MASTER_KEY = base64.b64encode(b"k" * 32).decode()


@pytest.fixture()
def executor_settings(tmp_path, monkeypatch):
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'agents.db').as_posix()}"
    monkeypatch.setenv("PROSEFORGE_DATABASE_URL", database_url)
    monkeypatch.setenv("PROSEFORGE_RUNTIME_PROFILE", "native")
    monkeypatch.setenv("PROSEFORGE_MASTER_KEY", MASTER_KEY)
    get_settings.cache_clear()
    yield Settings(
        database_url=database_url,
        runtime_profile="native",
        master_key=MASTER_KEY,
        blob_root=str(tmp_path / "blobs"),
        backup_root=str(tmp_path / "backups"),
    )
    get_settings.cache_clear()


class FakeProvider:
    """记录并发峰值与请求 metadata 的假 provider；可按 task_key 定制输出。"""

    provider_id = "fake"

    def __init__(self, payloads: dict[str, object] | None = None, usage: tuple[int, int] = (4, 2), delay: float = 0.0):
        self._payloads = payloads or {}
        self._input, self._output = usage
        self._delay = delay
        self.active = 0
        self.peak = 0
        self.requests: list[dict[str, str]] = []

    async def stream(self, request):
        self.active += 1
        self.peak = max(self.peak, self.active)
        self.requests.append(dict(request.metadata))
        try:
            if self._delay:
                await asyncio.sleep(self._delay)
            payload = self._payloads.get(request.metadata.get("task_key", ""), {"summary": "ok"})
            text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
            yield GenerationEvent("response.started")
            yield GenerationEvent("content.delta", text=text)
            yield GenerationEvent("response.completed", data={"usage": {"input_tokens": self._input, "output_tokens": self._output, "total_tokens": self._input + self._output}})
        finally:
            self.active -= 1

    async def list_models(self):
        return []

    async def validate_credentials(self):
        return {"valid": True}

    async def count_tokens(self, request):
        return 1


def _patch_provider(monkeypatch, provider: FakeProvider) -> None:
    monkeypatch.setattr("proseforge.providers.factory.build_provider", lambda *args, **kwargs: provider)


async def _seed_run(settings: Settings, tasks: list[dict[str, object]], *, budget_limit: int = 1000, fault_mode: str | None = None, with_credential: bool = True) -> dict[str, str]:
    engine, factory = create_engine_and_sessionmaker(settings)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SqlAlchemyUnitOfWork(factory) as uow:
            user = await uow.users.create(f"agents-{uuid.uuid4().hex[:8]}@example.local", "hash-not-used", "ADMIN")
            if with_credential:
                credential_id = f"cred-{uuid.uuid4().hex[:8]}"
                associated = f"{user.id}:openai:{credential_id}".encode()
                encrypted = CredentialCipher(base64.b64decode(MASTER_KEY)).encrypt(json.dumps({"api_key": "sk-test"}).encode(), associated_data=associated)
                await uow.credentials.create(user.id, "openai", base64.b64encode(encrypted).decode(), record_id=credential_id)
            now = datetime.now(UTC)
            run = AgentRunModel(
                id=new_id(), user_id=user.id, project_id="project-1", goal_hash="g" * 64,
                graph_revision=1, status="PENDING", budget_limit=budget_limit, fault_mode=fault_mode,
                created_at=now, updated_at=now,
            )
            uow.session.add(run)
            for item in tasks:
                uow.session.add(AgentTaskModel(
                    id=new_id(), run_id=run.id, task_key=str(item["id"]), role=str(item["role"]),
                    status="PENDING", token_budget=int(item.get("token_budget", 1)),
                    depends_on=json.dumps(item.get("depends_on", [])),
                ))
            await uow.commit()
            return {"run_id": run.id, "user_id": user.id}
    finally:
        await engine.dispose()


async def _read_state(settings: Settings, run_id: str):
    # 只读事务退出时 __aexit__ 会 rollback 并过期实例——必须在会话内快照为 dict
    engine, factory = create_engine_and_sessionmaker(settings)
    try:
        async with SqlAlchemyUnitOfWork(factory) as uow:
            run = await uow.session.get(AgentRunModel, run_id)
            run_snapshot = {key: getattr(run, key) for key in ("id", "status", "terminal_reason", "budget_used", "budget_limit", "event_cursor", "checkpoint_id", "proposal_id", "fault_mode")}
            tasks = [
                {key: getattr(task, key) for key in ("id", "task_key", "role", "status", "attempts", "token_budget", "last_error")}
                for task in await uow.session.scalars(select(AgentTaskModel).where(AgentTaskModel.run_id == run_id).order_by(AgentTaskModel.id))
            ]
            events = [
                {key: getattr(event, key) for key in ("sequence", "event_type", "payload")}
                for event in await uow.session.scalars(select(AgentEventModel).where(AgentEventModel.run_id == run_id).order_by(AgentEventModel.sequence))
            ]
            artifacts = [
                {key: getattr(artifact, key) for key in ("id", "task_id", "artifact_type", "sha256", "provenance", "preview", "payload")}
                for artifact in await uow.session.scalars(select(AgentArtifactModel).where(AgentArtifactModel.run_id == run_id))
            ]
            return run_snapshot, tasks, events, artifacts
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_parallel_execution_dependency_order_and_measured_budget(executor_settings, monkeypatch):
    provider = FakeProvider(usage=(10, 5), delay=0.01)
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(executor_settings, [
        {"id": "planner", "role": "chief_planner", "token_budget": 10},
        {"id": "scene-a", "role": "scene_writer", "depends_on": ["planner"], "token_budget": 10},
        {"id": "scene-b", "role": "scene_writer", "depends_on": ["planner"], "token_budget": 10},
    ])

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "completed"
    run, tasks, events, artifacts = await _read_state(executor_settings, seeded["run_id"])
    assert run["status"] == "COMPLETED"
    assert {task["task_key"] for task in tasks if task["status"] == "SUCCEEDED"} == {"planner", "scene-a", "scene-b"}
    started = {json.loads(event["payload"])["task_key"]: event["sequence"] for event in events if event["event_type"] == "task.started"}
    succeeded = {json.loads(event["payload"])["task_key"]: event["sequence"] for event in events if event["event_type"] == "task.succeeded"}
    # 依赖就绪：planner 成功后两个 scene 才启动
    assert succeeded["planner"] < started["scene-a"]
    assert succeeded["planner"] < started["scene-b"]
    # 有界并行：两个 scene 并发执行且峰值不超上限
    assert provider.peak >= 2
    assert provider.peak <= MAX_PARALLEL_TASKS
    # 实测 usage 结算：3 任务 × (10+5)=45，不是申报的 3×10
    assert run["budget_used"] == 45
    usage_events = [json.loads(event["payload"]) for event in events if event["event_type"] == "task.usage"]
    assert sum(item["total_tokens"] for item in usage_events) == 45
    assert all(item["input_tokens"] == 10 and item["output_tokens"] == 5 for item in usage_events)
    # 每任务恰好一个 artifact；sha256 为 canonical JSON；provenance 含 task_id/role/model
    assert len(artifacts) == 3
    for artifact in artifacts:
        assert artifact["sha256"] == hashlib.sha256(artifact["payload"].encode()).hexdigest()
        assert artifact["artifact_type"] == "candidate"
        assert {"task_id", "role", "model"} <= set(json.loads(artifact["provenance"]))
        assert len(artifact["preview"]) <= 80
    # run.checkpoint_id 契约：graph 版本 + done 列表 + 事件游标 + 执行器版本
    match = re.fullmatch(r"graph:(\d+)\|done:([^|]*)\|cursor:(\d+)\|exec:(\S+)", run["checkpoint_id"] or "")
    assert match is not None
    assert match.group(1) == "1"
    assert set(match.group(2).split(",")) == {"planner", "scene-a", "scene-b"}
    # cursor 记录最后一次任务提交时的事件游标；终态 run.completed 事件在其后 +1
    assert int(match.group(3)) == run["event_cursor"] - 1
    assert match.group(4) == EXECUTOR_VERSION
    # metadata 携带 role/task_key（mock provider 后续可按角色分支）
    assert all({"role", "task_key"} <= set(request) for request in provider.requests)
    # 新事件类型加入且旧词表完整
    event_types = {event["event_type"] for event in events}
    assert {"run.started", "task.started", "task.lease_acquired", "task.usage", "artifact.committed", "task.succeeded", "run.completed"} <= event_types
    sequences = [event["sequence"] for event in events]
    assert len(set(sequences)) == len(sequences)


@pytest.mark.asyncio
async def test_parallel_claim_respects_semaphore(executor_settings, monkeypatch):
    provider = FakeProvider(usage=(1, 1), delay=0.02)
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(
        executor_settings,
        [{"id": f"task-{index:02d}", "role": "scene_writer", "token_budget": 1} for index in range(MAX_PARALLEL_TASKS + 4)],
        budget_limit=1000,
    )

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "completed"
    run, tasks, _events, artifacts = await _read_state(executor_settings, seeded["run_id"])
    assert provider.peak == MAX_PARALLEL_TASKS  # 认领上限即并发上限
    assert all(task["status"] == "SUCCEEDED" for task in tasks)
    assert len(artifacts) == MAX_PARALLEL_TASKS + 4
    assert run["budget_used"] == 2 * (MAX_PARALLEL_TASKS + 4)


@pytest.mark.asyncio
async def test_artifact_schema_rejection_fails_task_but_run_continues(executor_settings, monkeypatch):
    from proseforge.application.agents.role_handlers import ROLE_HANDLERS, RoleResult

    async def bad_specialist(_context):
        # scene_writer 的 RolePolicy allowlist 是 {report, candidate}，SceneDraft 必被拒
        return RoleResult(artifact_type="SceneDraft", payload={"title": "只有标题"}, used_tokens=3)

    monkeypatch.setitem(ROLE_HANDLERS, "scene_writer", bad_specialist)
    provider = FakeProvider(usage=(2, 1))
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(executor_settings, [
        {"id": "bad-scene", "role": "scene_writer", "token_budget": 1},
        {"id": "planner", "role": "chief_planner", "token_budget": 1},
        {"id": "follow", "role": "continuity_reviewer", "depends_on": ["planner"], "token_budget": 1},
    ])

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "failed"
    run, tasks, events, artifacts = await _read_state(executor_settings, seeded["run_id"])
    status_by_key = {task["task_key"]: task["status"] for task in tasks}
    # 校验失败只杀该任务，run 继续其余任务后才以 FAILED 收场
    assert status_by_key == {"bad-scene": "FAILED", "planner": "SUCCEEDED", "follow": "SUCCEEDED"}
    assert run["status"] == "FAILED"
    assert run["terminal_reason"] == "task(s) failed without retry"
    assert len(artifacts) == 2  # 被拒任务不落 artifact
    failed_events = [json.loads(event["payload"]) for event in events if event["event_type"] == "task.failed"]
    assert len(failed_events) == 1
    assert "not allowed for role scene_writer" in failed_events[0]["error"]
    assert failed_events[0]["retry"] is False
    assert any(event["event_type"] == "run.failed" for event in events)


@pytest.mark.asyncio
async def test_malformed_output_retries_then_task_fails(executor_settings, monkeypatch):
    provider = FakeProvider(payloads={"fragile": "<<not json>>"}, usage=(1, 1))
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(executor_settings, [{"id": "fragile", "role": "chief_planner", "token_budget": 1}])

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "failed"
    run, tasks, events, artifacts = await _read_state(executor_settings, seeded["run_id"])
    task = tasks[0]
    assert task["status"] == "FAILED"
    assert task["attempts"] == DEFAULT_MAX_ATTEMPTS  # 重试耗尽才 FAILED
    assert "JSONDecodeError" in (task["last_error"] or "")
    assert run["status"] == "FAILED"
    assert run["terminal_reason"] == "task(s) failed without retry"
    assert artifacts == []
    failed_events = [json.loads(event["payload"]) for event in events if event["event_type"] == "task.failed"]
    assert [item["retry"] for item in failed_events] == [True, True, False]


@pytest.mark.asyncio
async def test_fault_provider_timeout_still_raises(executor_settings):
    seeded = await _seed_run(executor_settings, [{"id": "planner", "role": "chief_planner", "token_budget": 1}], fault_mode="provider_timeout")

    with pytest.raises(TimeoutError):
        await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    run, _tasks, events, _artifacts = await _read_state(executor_settings, seeded["run_id"])
    assert run["status"] == "FAILED"
    assert run["terminal_reason"] == "TimeoutError"
    assert any(event["event_type"] == "run.failed" for event in events)


@pytest.mark.asyncio
async def test_fault_malformed_json_still_raises(executor_settings):
    seeded = await _seed_run(executor_settings, [{"id": "planner", "role": "chief_planner", "token_budget": 1}], fault_mode="malformed_json")

    with pytest.raises(json.JSONDecodeError):
        await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    run, _tasks, events, _artifacts = await _read_state(executor_settings, seeded["run_id"])
    assert run["status"] == "FAILED"
    assert run["terminal_reason"] == "JSONDecodeError"
    assert any(event["event_type"] == "run.failed" for event in events)


@pytest.mark.asyncio
async def test_fault_budget_exhaustion_stays_durable(executor_settings):
    seeded = await _seed_run(executor_settings, [{"id": "planner", "role": "chief_planner", "token_budget": 1}], fault_mode="budget_exhaustion")

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "budget-exhausted"
    run, _tasks, events, _artifacts = await _read_state(executor_settings, seeded["run_id"])
    assert run["status"] == "BUDGET_EXHAUSTED"
    assert run["terminal_reason"] == "injected budget exhaustion"
    assert any(event["event_type"] == "run.budget_exhausted" for event in events)


@pytest.mark.asyncio
async def test_missing_credential_fails_run_without_crash(executor_settings, monkeypatch):
    provider = FakeProvider()
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(executor_settings, [{"id": "planner", "role": "chief_planner", "token_budget": 1}], with_credential=False)

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "provider-or-project-not-configured"
    run, tasks, events, _artifacts = await _read_state(executor_settings, seeded["run_id"])
    assert run["status"] == "FAILED"
    assert run["terminal_reason"] == "provider-or-project-not-configured"
    assert tasks[0]["status"] == "PENDING"  # 任务退回 PENDING，配置后可重试
    assert provider.requests == []  # 未发生模型调用
    assert any(event["event_type"] == "run.failed" for event in events)
