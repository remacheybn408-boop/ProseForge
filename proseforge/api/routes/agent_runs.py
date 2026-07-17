from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.agents.validate_graph import validate_graph
from proseforge.application.auth.service import AuthUser
from proseforge.domain.agents.task_graph import AgentTaskSpec, TaskGraph
from proseforge.domain.agents.roles import AgentRole
from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.agents import AgentArtifactModel, AgentEventModel, AgentPolicySnapshotModel, AgentReviewModel, AgentRunModel, AgentTaskModel
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v3", tags=["agent-runs"])


class GraphTaskRequest(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    role: str = Field(min_length=1, max_length=64)
    depends_on: list[str] = Field(default_factory=list, max_length=8)
    output_artifact_type: str = Field(default="report", max_length=100)
    token_budget: int = Field(default=1, ge=1, le=12000)


class AgentRunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=12000)
    graph_revision: int = Field(default=1, ge=1)
    tasks: list[GraphTaskRequest] = Field(default_factory=list, max_length=64)
    budget_limit: int = Field(default=12000, ge=1, le=100000)
    chapter_id: str | None = None
    base_version_id: str | None = None
    fault_mode: Literal["provider_timeout", "malformed_json", "budget_exhaustion", "crash_after_artifact_commit"] | None = None


class ArtifactRequest(BaseModel):
    task_id: str | None = None
    artifact_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, object] = Field(default_factory=dict)
    provenance: dict[str, object] = Field(default_factory=dict)
    preview: str = Field(default="", max_length=500)


class ReviewRequest(BaseModel):
    artifact_id: str
    reviewer_role: str
    status: str = Field(pattern=r"^(PASS|WARNING|CONFLICT|UNSUPPORTED)$")
    evidence: list[dict[str, object]] = Field(default_factory=list, max_length=32)
    conflict_group: str | None = None


def _run_response(run: AgentRunModel) -> dict[str, object]:
    return {
        "id": run.id, "project_id": run.project_id, "status": run.status,
        "goal_hash": run.goal_hash, "graph_revision": run.graph_revision,
        "checkpoint_id": run.checkpoint_id, "budget_used": run.budget_used,
        "budget_limit": run.budget_limit, "event_cursor": run.event_cursor,
        "policy_version": run.policy_version, "terminal_reason": run.terminal_reason,
        "chapter_id": run.chapter_id, "base_version_id": run.base_version_id, "proposal_id": run.proposal_id,
        "fault_mode": run.fault_mode,
    }


async def _owned_run(uow: SqlAlchemyUnitOfWork, run_id: str, user_id: str) -> AgentRunModel:
    run = await uow.session.scalar(select(AgentRunModel).where(AgentRunModel.id == run_id, AgentRunModel.user_id == user_id))
    if run is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    return run


async def _event(uow: SqlAlchemyUnitOfWork, run: AgentRunModel, event_type: str, payload: dict[str, object] | None = None) -> None:
    locked = await uow.session.scalar(
        select(AgentRunModel)
        .where(AgentRunModel.id == run.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if locked is None:
        raise HTTPException(status_code=404, detail="agent run not found")
    sequence = locked.event_cursor + 1
    uow.session.add(AgentEventModel(id=new_id(), run_id=locked.id, sequence=sequence, event_type=event_type, payload=json.dumps(payload or {}, ensure_ascii=False, sort_keys=True)))
    locked.event_cursor = sequence
    locked.updated_at = datetime.now(UTC)


@router.post("/projects/{project_id}/agent-runs", status_code=status.HTTP_201_CREATED)
async def start_run(
    project_id: str,
    payload: AgentRunRequest,
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> dict[str, object]:
    tasks = payload.tasks or [GraphTaskRequest(id="planner", role="chief_planner"), GraphTaskRequest(id="reviewer", role="continuity_reviewer", depends_on=["planner"])]
    graph = TaskGraph(payload.graph_revision, tuple(AgentTaskSpec(item.id, item.role, tuple(item.depends_on), output_artifact_type=item.output_artifact_type, token_budget=item.token_budget) for item in tasks))
    try:
        validate_graph(graph)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if sum(item.token_budget for item in tasks) > payload.budget_limit:
        raise HTTPException(status_code=422, detail="graph token budget exceeds run budget")
    async with uow:
        if payload.fault_mode and request.app.state.settings.environment.lower() in {"production", "prod"}:
            raise HTTPException(status_code=422, detail="fault injection is disabled in production")
        project = await uow.projects.get_by_id(user.id, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        if idempotency_key:
            existing = await uow.session.scalar(select(AgentRunModel).where(AgentRunModel.user_id == user.id, AgentRunModel.project_id == project_id, AgentRunModel.idempotency_key == idempotency_key))
            if existing is not None:
                return _run_response(existing)
        now = datetime.now(UTC)
        if payload.chapter_id is not None:
            chapter = await uow.chapters.get_owned(payload.chapter_id, user.id)
            if chapter is None or chapter.project_id != project_id:
                raise HTTPException(status_code=404, detail="chapter not found")
        run = AgentRunModel(id=new_id(), user_id=user.id, project_id=project_id, chapter_id=payload.chapter_id, base_version_id=payload.base_version_id, fault_mode=payload.fault_mode, goal_hash=hashlib.sha256(payload.goal.encode()).hexdigest(), idempotency_key=idempotency_key, graph_revision=payload.graph_revision, status="PENDING", budget_limit=payload.budget_limit, created_at=now, updated_at=now)
        uow.session.add(run)
        policy_payload = {"roles": sorted(role.value for role in AgentRole), "version": "v3-policy-1"}
        policy_json = json.dumps(policy_payload, sort_keys=True)
        run.policy_version = policy_payload["version"]
        uow.session.add(AgentPolicySnapshotModel(id=new_id(), run_id=run.id, policy_version=run.policy_version, policy_hash=hashlib.sha256(policy_json.encode()).hexdigest(), payload=policy_json))
        for item in tasks:
            uow.session.add(AgentTaskModel(id=new_id(), run_id=run.id, task_key=item.id, role=item.role, status="PENDING", token_budget=item.token_budget, depends_on=json.dumps(item.depends_on), checkpoint_id=None))
        await _event(uow, run, "run.created", {"graph_revision": payload.graph_revision, "task_count": len(tasks)})
        await uow.commit()
        try:
            await request.app.state.queue.enqueue("proseforge.agents.execute_run", {"run_id": run.id, "user_id": user.id})
        except Exception as exc:
            run.status = "FAILED"
            run.terminal_reason = "queue unavailable"
            await _event(uow, run, "run.queue_failed", {"error": type(exc).__name__})
            await uow.commit()
            raise HTTPException(status_code=503, detail="agent queue unavailable") from exc
        return _run_response(run)


@router.get("/agent-runs/{run_id}")
async def get_run(run_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        return _run_response(await _owned_run(uow, run_id, user.id))


async def _control(run_id: str, action: str, user: AuthUser, uow: SqlAlchemyUnitOfWork, task_id: str | None = None, queue=None) -> dict[str, object]:
    run = await _owned_run(uow, run_id, user.id)
    transitions = {"pause": ("PAUSED", {"PENDING", "RUNNING"}), "resume": ("RUNNING", {"PENDING", "PAUSED", "FAILED"}), "cancel": ("CANCELLED", {"PENDING", "RUNNING", "PAUSED", "FAILED"})}
    if action == "retry":
        if run.status not in {"FAILED", "PAUSED", "RUNNING"}:
            raise HTTPException(status_code=409, detail="run is not retryable")
        if task_id:
            task = await uow.session.scalar(select(AgentTaskModel).where(AgentTaskModel.id == task_id, AgentTaskModel.run_id == run.id))
            if task is None:
                raise HTTPException(status_code=404, detail="task not found")
            task.status, task.attempts, task.last_error = "PENDING", task.attempts + 1, None
        run.status = "RUNNING"
        await _event(uow, run, "run.retry", {"task_id": task_id})
    else:
        target, allowed = transitions[action]
        if run.status == target:
            return _run_response(run)
        if run.status not in allowed:
            raise HTTPException(status_code=409, detail="invalid run transition")
        run.status = target
        if target == "CANCELLED":
            run.terminal_reason = "cancelled by user"
        await _event(uow, run, f"run.{action}")
    await uow.commit()
    if action in {"resume", "retry"} and queue is not None:
        await queue.enqueue("proseforge.agents.execute_run", {"run_id": run.id, "user_id": user.id})
    return _run_response(run)


def _make_control_handler(action: str):
    async def handler(
        run_id: str,
        request: Request,
        user: Annotated[AuthUser, Depends(current_user)],
        uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
    ):
        async with uow:
            return await _control(run_id, action, user, uow, queue=request.app.state.queue)

    handler.__name__ = f"{action}_agent_run"
    return handler


for _action in ("pause", "resume", "cancel"):
    router.add_api_route(f"/agent-runs/{{run_id}}/{_action}", _make_control_handler(_action), methods=["POST"])


@router.post("/agent-runs/{run_id}/retry")
async def retry_run(run_id: str, request: Request, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)], task_id: str | None = None) -> dict[str, object]:
    async with uow:
        return await _control(run_id, "retry", user, uow, task_id, request.app.state.queue)


@router.get("/agent-runs/{run_id}/tasks")
async def list_tasks(run_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> list[dict[str, object]]:
    async with uow:
        await _owned_run(uow, run_id, user.id)
        rows = await uow.session.scalars(select(AgentTaskModel).where(AgentTaskModel.run_id == run_id).order_by(AgentTaskModel.id))
        return [{"id": row.id, "task_key": row.task_key, "role": row.role, "status": row.status, "attempts": row.attempts, "token_budget": row.token_budget, "depends_on": json.loads(row.depends_on)} for row in rows]


@router.get("/agent-runs/{run_id}/events")
async def list_events(run_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)], after: int = 0) -> dict[str, object]:
    async with uow:
        await _owned_run(uow, run_id, user.id)
        rows = await uow.session.scalars(select(AgentEventModel).where(AgentEventModel.run_id == run_id, AgentEventModel.sequence > max(0, after)).order_by(AgentEventModel.sequence))
        events = [{"id": row.id, "sequence": row.sequence, "event": row.event_type, "data": json.loads(row.payload)} for row in rows]
        return {"events": events, "next_cursor": events[-1]["sequence"] if events else max(0, after)}


@router.post("/agent-runs/{run_id}/artifacts", status_code=status.HTTP_201_CREATED)
async def create_artifact(run_id: str, payload: ArtifactRequest, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        run = await _owned_run(uow, run_id, user.id)
        raw = json.dumps(payload.payload, ensure_ascii=False, sort_keys=True).encode()
        artifact = AgentArtifactModel(id=new_id(), run_id=run.id, task_id=payload.task_id, artifact_type=payload.artifact_type, sha256=hashlib.sha256(raw).hexdigest(), provenance=json.dumps(payload.provenance, sort_keys=True), preview=payload.preview, payload=json.dumps(payload.payload, ensure_ascii=False))
        uow.session.add(artifact)
        await _event(uow, run, "artifact.committed", {"artifact_id": artifact.id, "sha256": artifact.sha256})
        await uow.commit()
        return {"id": artifact.id, "artifact_type": artifact.artifact_type, "sha256": artifact.sha256, "preview": artifact.preview, "provenance": json.loads(artifact.provenance)}


@router.get("/agent-runs/{run_id}/artifacts")
async def list_artifacts(run_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> list[dict[str, object]]:
    async with uow:
        await _owned_run(uow, run_id, user.id)
        rows = await uow.session.scalars(select(AgentArtifactModel).where(AgentArtifactModel.run_id == run_id).order_by(AgentArtifactModel.id))
        return [{"id": row.id, "artifact_type": row.artifact_type, "sha256": row.sha256, "preview": row.preview, "provenance": json.loads(row.provenance)} for row in rows]


@router.post("/agent-runs/{run_id}/reviews", status_code=status.HTTP_201_CREATED)
async def create_review(run_id: str, payload: ReviewRequest, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> dict[str, object]:
    async with uow:
        await _owned_run(uow, run_id, user.id)
        artifact = await uow.session.scalar(select(AgentArtifactModel).where(AgentArtifactModel.id == payload.artifact_id, AgentArtifactModel.run_id == run_id))
        if artifact is None:
            raise HTTPException(status_code=404, detail="artifact not found")
        if not payload.evidence and payload.status != "UNSUPPORTED":
            raise HTTPException(status_code=422, detail="review evidence is required")
        review = AgentReviewModel(id=new_id(), run_id=run_id, artifact_id=payload.artifact_id, reviewer_role=payload.reviewer_role, status=payload.status, evidence=json.dumps(payload.evidence), conflict_group=payload.conflict_group, payload="{}")
        uow.session.add(review)
        await uow.commit()
        return {"id": review.id, "artifact_id": review.artifact_id, "status": review.status, "evidence": payload.evidence, "conflict_group": review.conflict_group}


@router.get("/agent-runs/{run_id}/reviews")
async def list_reviews(run_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> list[dict[str, object]]:
    async with uow:
        await _owned_run(uow, run_id, user.id)
        rows = await uow.session.scalars(select(AgentReviewModel).where(AgentReviewModel.run_id == run_id).order_by(AgentReviewModel.id))
        return [{"id": row.id, "artifact_id": row.artifact_id, "reviewer_role": row.reviewer_role, "status": row.status, "evidence": json.loads(row.evidence), "conflict_group": row.conflict_group} for row in rows]


@router.get("/agent-runs/{run_id}/audit")
async def audit_run(run_id: str, user: Annotated[AuthUser, Depends(current_user)], uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)]) -> list[dict[str, object]]:
    async with uow:
        await _owned_run(uow, run_id, user.id)
        rows = await uow.session.scalars(select(AgentEventModel).where(AgentEventModel.run_id == run_id).order_by(AgentEventModel.sequence))
        return [{"sequence": row.sequence, "event": row.event_type, "payload": json.loads(row.payload)} for row in rows]
