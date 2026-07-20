"""WS-D 评审簇 handler（review_handlers.py）宿主可跑测试。

sqlite+aiosqlite 真实落库 + FakeProvider 假模型（无网络、无 PG），
settings/credential 种子模式复制自 tests/agents/test_agent_executor.py（WS-A）。
覆盖：评审行持久化（证据规则）、冲突接线（共享 conflict_group）、UNSUPPORTED、
policy.denied fail-closed、merge_editor 四桶分类（不改写正文、不调模型）。
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from proseforge.domain.common.ids import new_id
from proseforge.domain.ports.model_provider import GenerationEvent
from proseforge.infrastructure.database.base import Base
from proseforge.infrastructure.database.models.agents import AgentArtifactModel, AgentEventModel, AgentReviewModel, AgentRunModel, AgentTaskModel
from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.infrastructure.security.credential_cipher import CredentialCipher
from proseforge.settings import Settings, get_settings
from proseforge.workflows.agent_executor import execute_run

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
    """按 task_key 定制输出的假 provider（复制自 WS-A test_agent_executor.py）。"""

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


async def _seed_run(settings: Settings, tasks: list[dict[str, object]], *, budget_limit: int = 1000, status: str = "PENDING", artifacts: list[dict[str, object]] | None = None, reviews: list[dict[str, object]] | None = None) -> dict[str, str]:
    engine, factory = create_engine_and_sessionmaker(settings)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SqlAlchemyUnitOfWork(factory) as uow:
            user = await uow.users.create(f"agents-{uuid.uuid4().hex[:8]}@example.local", "hash-not-used", "ADMIN")
            credential_id = f"cred-{uuid.uuid4().hex[:8]}"
            associated = f"{user.id}:openai:{credential_id}".encode()
            encrypted = CredentialCipher(base64.b64decode(MASTER_KEY)).encrypt(json.dumps({"api_key": "sk-test"}).encode(), associated_data=associated)
            await uow.credentials.create(user.id, "openai", base64.b64encode(encrypted).decode(), record_id=credential_id)
            now = datetime.now(UTC)
            run = AgentRunModel(
                id=new_id(), user_id=user.id, project_id="project-1", goal_hash="g" * 64,
                graph_revision=1, status=status, budget_limit=budget_limit,
                created_at=now, updated_at=now,
            )
            uow.session.add(run)
            for item in tasks:
                uow.session.add(AgentTaskModel(
                    id=new_id(), run_id=run.id, task_key=str(item["id"]), role=str(item["role"]),
                    status="PENDING", token_budget=int(item.get("token_budget", 1)),
                    depends_on=json.dumps(item.get("depends_on", [])),
                ))
            for item in artifacts or []:
                raw = json.dumps(item.get("payload", {"summary": "seed"}), ensure_ascii=False, sort_keys=True)
                uow.session.add(AgentArtifactModel(
                    id=str(item["id"]), run_id=run.id, task_id=None,
                    artifact_type=str(item.get("artifact_type", "candidate")),
                    sha256=hashlib.sha256(raw.encode()).hexdigest(),
                    provenance="{}", preview=str(item.get("preview", "seed artifact"))[:80], payload=raw,
                ))
            for item in reviews or []:
                uow.session.add(AgentReviewModel(
                    id=str(item["id"]), run_id=run.id, artifact_id=str(item.get("artifact_id", "art-1")),
                    reviewer_role=str(item.get("reviewer_role", "continuity_reviewer")), status=str(item["status"]),
                    evidence=json.dumps(item.get("evidence", []), ensure_ascii=False),
                    conflict_group=item.get("conflict_group"),
                    payload=json.dumps(item.get("payload", {}), ensure_ascii=False),
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
            run_snapshot = {key: getattr(run, key) for key in ("id", "status", "terminal_reason", "budget_used", "proposal_id")}
            tasks = [
                {key: getattr(task, key) for key in ("id", "task_key", "role", "status", "attempts", "last_error")}
                for task in await uow.session.scalars(select(AgentTaskModel).where(AgentTaskModel.run_id == run_id).order_by(AgentTaskModel.id))
            ]
            events = [
                {key: getattr(event, key) for key in ("sequence", "event_type", "payload")}
                for event in await uow.session.scalars(select(AgentEventModel).where(AgentEventModel.run_id == run_id).order_by(AgentEventModel.sequence))
            ]
            artifacts = [
                {key: getattr(artifact, key) for key in ("id", "task_id", "artifact_type", "payload")}
                for artifact in await uow.session.scalars(select(AgentArtifactModel).where(AgentArtifactModel.run_id == run_id))
            ]
            reviews = [
                {key: getattr(review, key) for key in ("id", "artifact_id", "reviewer_role", "status", "evidence", "conflict_group", "payload")}
                for review in await uow.session.scalars(select(AgentReviewModel).where(AgentReviewModel.run_id == run_id))
            ]
            return run_snapshot, tasks, events, artifacts, reviews
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_reviewer_persists_reviews_with_evidence_and_events(executor_settings, monkeypatch):
    provider = FakeProvider(payloads={
        "planner": {"title": "t", "chapters": [{"title": "c1", "summary": "s"}]},
        "scene": {"title": "回城", "content": "雨夜，主角回城。"},
        "review": {
            "summary": "连续性检查",
            "findings": [{"finding": "主角位置前后矛盾", "severity": "high", "evidence_spans": [{"artifact_id": "", "start": 0, "end": 2, "quote": "雨夜"}], "verdict": "WARNING"}],
        },
    })
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(executor_settings, [
        {"id": "planner", "role": "chief_planner", "token_budget": 10},
        {"id": "scene", "role": "scene_writer", "depends_on": ["planner"], "token_budget": 10},
        {"id": "review", "role": "continuity_reviewer", "depends_on": ["scene"], "token_budget": 10},
    ])

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "completed"
    run, tasks, events, artifacts, reviews = await _read_state(executor_settings, seeded["run_id"])
    assert run["status"] == "COMPLETED"
    # 评审 claim 时上游已有 planner+scene 两个 artifact → 每个 artifact 一行评审
    assert len(reviews) == 2
    review_ids = {review["id"] for review in reviews}
    statuses = sorted(review["status"] for review in reviews)
    assert statuses == ["PASS", "WARNING"]
    warning = next(review for review in reviews if review["status"] == "WARNING")
    warning_evidence = json.loads(warning["evidence"])
    assert any(span.get("quote") == "雨夜" for span in warning_evidence)
    # 证据规则：PASS/WARNING 必须带证据
    passing = next(review for review in reviews if review["status"] == "PASS")
    assert json.loads(passing["evidence"])
    assert all(review["conflict_group"] is None for review in reviews)
    # review.committed 事件逐行发出，携带状态与 conflict_group 键
    committed = [json.loads(event["payload"]) for event in events if event["event_type"] == "review.committed"]
    assert len(committed) == 2
    assert {item["review_id"] for item in committed} == review_ids
    assert all({"reviewer_role", "status", "conflict_group"} <= set(item) for item in committed)
    # 评审 artifact：artifact_type=report（RolePolicy allowlist），payload 承载类型化报告键
    review_artifact = next(artifact for artifact in artifacts if json.loads(artifact["payload"]).get("report_type") == "ContinuityReport")
    assert review_artifact["artifact_type"] == "report"
    payload = json.loads(review_artifact["payload"])
    assert payload["verdict"] == "WARNING"
    assert len(payload["issues"]) == 1  # ContinuityReport required key 承载 findings
    assert set(payload["review_ids"]) == review_ids


@pytest.mark.asyncio
async def test_conflicting_reviewers_share_conflict_group(executor_settings, monkeypatch):
    provider = FakeProvider(payloads={
        "scene": {"title": "回城", "content": "雨夜，主角回城。"},
        "continuity": {"summary": "s", "findings": [{"finding": "主角此时在城内", "severity": "high", "evidence_spans": [{"artifact_id": "", "start": 0, "end": 2, "quote": "雨夜"}], "verdict": "WARNING"}]},
        "adversarial": {"summary": "s", "findings": [{"finding": "主角此时在城外", "severity": "high", "evidence_spans": [{"artifact_id": "", "start": 0, "end": 2, "quote": "雨夜"}], "verdict": "WARNING"}]},
    })
    _patch_provider(monkeypatch, provider)
    # 顺序执行（adversarial 依赖 continuity）：后到者在同一证据上看到先到者的相反主张
    seeded = await _seed_run(executor_settings, [
        {"id": "scene", "role": "scene_writer", "token_budget": 10},
        {"id": "continuity", "role": "continuity_reviewer", "depends_on": ["scene"], "token_budget": 10},
        {"id": "adversarial", "role": "adversarial_reviewer", "depends_on": ["continuity"], "token_budget": 10},
    ])

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "completed"
    _run, _tasks, events, _artifacts, reviews = await _read_state(executor_settings, seeded["run_id"])
    # adversarial 的上游快照含 scene artifact + continuity 的评审报告 → 3 行评审
    assert len(reviews) == 3
    # 同一证据 quote、不同结论 → 两条 scene 评审 CONFLICT 且共享确定性 conflict_group；
    # adversarial 对 continuity 报告的评审无主张 → PASS（不冲突）
    conflicted = [review for review in reviews if review["status"] == "CONFLICT"]
    assert len(conflicted) == 2
    groups = {review["conflict_group"] for review in conflicted}
    assert len(groups) == 1
    assert groups.pop().startswith("cg-")
    assert sorted(review["status"] for review in reviews) == ["CONFLICT", "CONFLICT", "PASS"]
    committed = [json.loads(event["payload"]) for event in events if event["event_type"] == "review.committed"]
    assert len(committed) == 3
    assert any(item["conflict_group"] for item in committed)
    # 双方主张都保留在评审行 payload 里（冲突保留，不删改任何一方）
    claims = [claim["finding"] for review in reviews for claim in json.loads(review["payload"])["claims"]]
    assert sorted(claims) == ["主角此时在城内", "主角此时在城外"]


@pytest.mark.asyncio
async def test_findings_without_evidence_become_unsupported(executor_settings, monkeypatch):
    provider = FakeProvider(payloads={
        "scene": {"title": "回城", "content": "雨夜，主角回城。"},
        "review": {"summary": "s", "findings": [{"finding": "疑似设定矛盾", "severity": "low"}]},
    })
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(executor_settings, [
        {"id": "scene", "role": "scene_writer", "token_budget": 10},
        {"id": "review", "role": "continuity_reviewer", "depends_on": ["scene"], "token_budget": 10},
    ])

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "completed"
    _run, _tasks, _events, artifacts, reviews = await _read_state(executor_settings, seeded["run_id"])
    assert len(reviews) == 1
    review = reviews[0]
    # 无证据区间的 finding → UNSUPPORTED，且只有 UNSUPPORTED 允许空证据
    assert review["status"] == "UNSUPPORTED"
    assert json.loads(review["evidence"]) == []
    payload = json.loads(next(artifact for artifact in artifacts if json.loads(artifact["payload"]).get("report_type"))["payload"])
    assert payload["verdict"] == "UNSUPPORTED"


@pytest.mark.asyncio
async def test_policy_denial_fails_task_without_retry(executor_settings, monkeypatch):
    from proseforge.domain.agents import policy

    real_authorize = policy.authorize

    def denying_authorize(role, capability, **kwargs):
        if str(role) == "continuity_reviewer":
            raise policy.PolicyDenied("continuity_reviewer cannot create_artifact (test injection)")
        return real_authorize(role, capability, **kwargs)

    monkeypatch.setattr(policy, "authorize", denying_authorize)
    provider = FakeProvider()
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(executor_settings, [
        {"id": "planner", "role": "chief_planner", "token_budget": 10},
        {"id": "review", "role": "continuity_reviewer", "depends_on": ["planner"], "token_budget": 10},
    ])

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "failed"
    run, tasks, events, artifacts, reviews = await _read_state(executor_settings, seeded["run_id"])
    status_by_key = {task["task_key"]: task["status"] for task in tasks}
    assert status_by_key == {"planner": "SUCCEEDED", "review": "FAILED"}
    denied_task = next(task for task in tasks if task["task_key"] == "review")
    assert denied_task["attempts"] == 1  # 策略拒绝是确定性的：不重试
    assert "PolicyDenied" in (denied_task["last_error"] or "")
    denied_events = [json.loads(event["payload"]) for event in events if event["event_type"] == "policy.denied"]
    assert len(denied_events) == 1
    assert denied_events[0]["decision"] == "deny"
    assert "cannot create_artifact" in denied_events[0]["reason"]
    assert run["status"] == "FAILED"
    assert len(artifacts) == 1  # 只有 planner 的 artifact；被拒任务不落库
    assert reviews == []  # 被拒评审不写任何评审行


@pytest.mark.asyncio
async def test_merge_editor_categorizes_stored_reviews(executor_settings, monkeypatch):
    provider = FakeProvider()
    _patch_provider(monkeypatch, provider)
    seeded = await _seed_run(
        executor_settings,
        [{"id": "merge", "role": "merge_editor", "token_budget": 10}],
        artifacts=[{"id": "art-1", "artifact_type": "candidate", "preview": "scene draft"}],
        reviews=[
            {"id": "r-pass", "status": "PASS", "evidence": [{"quote": "a"}], "payload": {"claims": [], "resolution": None}},
            {"id": "r-warn", "status": "WARNING", "evidence": [{"quote": "b"}], "payload": {"claims": [{"finding": "f2", "severity": "low"}], "resolution": None}},
            {"id": "r-left", "status": "CONFLICT", "conflict_group": "cg-x", "evidence": [{"quote": "雨夜"}], "payload": {"claims": [{"finding": "left"}], "resolution": None}},
            {"id": "r-right", "status": "CONFLICT", "conflict_group": "cg-x", "evidence": [{"quote": "雨夜"}], "payload": {"claims": [{"finding": "right"}], "resolution": None}},
            {"id": "r-unsup", "status": "UNSUPPORTED", "evidence": [], "payload": {"claims": [{"finding": "f5"}], "resolution": None}},
            {"id": "r-accept", "status": "WARNING", "evidence": [{"quote": "c"}], "payload": {"claims": [{"finding": "f6"}], "resolution": "accepted"}},
        ],
    )

    result = await execute_run({"run_id": seeded["run_id"], "user_id": seeded["user_id"]})

    assert result == "completed"
    run, tasks, events, artifacts, _reviews = await _read_state(executor_settings, seeded["run_id"])
    assert run["status"] == "COMPLETED"
    assert provider.requests == []  # merge_editor 纯分类，不调模型
    assert len(artifacts) == 2  # 种子 artifact + MergeCandidate
    candidate = next(artifact for artifact in artifacts if artifact["id"] != "art-1")
    assert candidate["artifact_type"] == "candidate"
    payload = json.loads(candidate["payload"])
    # 四桶分类：PASS/WARNING→agreements；CONFLICT 同组聚合；UNSUPPORTED；resolution=accepted→accepted
    assert {item["review_id"] for item in payload["agreements"]} == {"r-pass", "r-warn"}
    assert len(payload["conflicts"]) == 1
    conflict = payload["conflicts"][0]
    assert conflict["conflict_group"] == "cg-x"
    assert conflict["parties"] == ["r-left", "r-right"]
    assert conflict["resolution"] is None
    assert {claim["finding"] for claim in conflict["claims"]} == {"left", "right"}
    assert [item["review_id"] for item in payload["unsupported"]] == ["r-unsup"]
    assert [item["review_id"] for item in payload["accepted"]] == ["r-accept"]
    assert sorted(payload["sources"]) == ["r-accept", "r-left", "r-pass", "r-right", "r-unsup", "r-warn"]
    assert "content" not in payload  # merge_editor 绝不改写作者正文
    merge_events = [json.loads(event["payload"]) for event in events if event["event_type"] == "merge.committed"]
    assert len(merge_events) == 1
    assert (merge_events[0]["agreements"], merge_events[0]["conflicts"], merge_events[0]["unsupported"], merge_events[0]["accepted"]) == (2, 1, 1, 1)
