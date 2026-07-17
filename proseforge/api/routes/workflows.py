from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.api.sse.encoder import encode_sse
from proseforge.application.auth.service import AuthUser
from proseforge.application.workflows.control import WorkflowControlService, workflow_command
from proseforge.application.workflows.event_stream import iter_workflow_events
from proseforge.domain.chapter.entity import Chapter
from proseforge.application.workflows.control import decode_checkpoint
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1", tags=["workflows"])


class NovelWorkflowRequest(BaseModel):
    chapter_numbers: list[int] = Field(default_factory=list, min_length=1)
    cost_limit: float = Field(default=0.0, ge=0)
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    editor_model: str | None = None
    token_limit: int = Field(default=0, ge=0)


def _response(run) -> dict[str, object]:
    checkpoint = decode_checkpoint(run.checkpoint)
    command = checkpoint.get("command") if isinstance(checkpoint.get("command"), dict) else {}
    phase = str(checkpoint.get("phase", run.checkpoint or run.status))
    requested = [int(item) for item in command.get("chapter_numbers", []) if isinstance(item, int | str) and str(item).isdigit()]
    completed = sorted({int(item) for item in checkpoint.get("completed_chapters", []) if isinstance(item, int | str) and str(item).isdigit()})
    current_match = re.search(r"CHAPTER_(\d+)", phase)
    current_chapter = int(current_match.group(1)) if current_match else None
    completed_steps = checkpoint.get("completed_steps")
    if not isinstance(completed_steps, list):
        completed_steps = []
    retry_count = checkpoint.get("retry_count", 0)
    if not isinstance(retry_count, int):
        retry_count = 0
    return {
        "id": run.id, "project_id": run.project_id, "workflow_type": run.workflow_type, "status": run.status,
        "estimated_cost": float(getattr(run, "estimated_cost", 0) or 0), "cost_limit": float(getattr(run, "cost_limit", 0) or 0),
        "used_tokens": int(getattr(run, "used_tokens", 0) or 0), "token_limit": int(getattr(run, "token_limit", 0) or 0),
        "checkpoint": phase, "last_error": getattr(run, "last_error", None),
        "current_step": phase,
        "completed_steps": [str(step) for step in completed_steps],
        "chapter_progress": {"current": current_chapter, "completed": completed, "total": len(requested), "requested": requested},
        "retry_count": retry_count,
        "model": command.get("model"),
        "editor_model": command.get("editor_model"),
        "token_cost_estimate": {
            "used_tokens": int(getattr(run, "used_tokens", 0) or 0),
            "token_limit": int(getattr(run, "token_limit", 0) or 0),
            "cost_usd": float(getattr(run, "estimated_cost", 0) or 0),
            "cost_limit": float(getattr(run, "cost_limit", 0) or 0),
        },
    }


@router.post("/projects/{project_id}/workflows/novel", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    project_id: str,
    payload: NovelWorkflowRequest,
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        project = await uow.projects.get_by_id(user.id, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        existing = {chapter.chapter_no for chapter in await uow.chapters.list_owned(project.id, user.id)}
        for chapter_no in payload.chapter_numbers:
            if chapter_no not in existing:
                await uow.chapters.add(Chapter.create(project_id=project.id, chapter_no=chapter_no, title=f"Chapter {chapter_no}"))
        return_value = await uow.workflows.create(project.id, "NOVEL", cost_limit=payload.cost_limit, token_limit=payload.token_limit)
        command = workflow_command(user_id=user.id, chapter_numbers=payload.chapter_numbers, provider=payload.provider, model=payload.model, editor_model=payload.editor_model or payload.model)
        await uow.workflows.set_command(return_value, command)
        await uow.commit()
        task_id = await request.app.state.queue.enqueue("proseforge.workflows.generate_novel", {"workflow_id": return_value.id, **command})
        await uow.workflows.set_task(return_value, task_id)
        await uow.commit()
        result = _response(return_value)
        result["task_id"] = task_id
        return result


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        run = await uow.workflows.get_owned(workflow_id, user.id)
        if run is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return _response(run)


@router.post("/workflows/{workflow_id}/{action}")
async def control_workflow(
    workflow_id: str,
    action: str,
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        try:
            result = await WorkflowControlService(uow, request.app.state.queue).execute(workflow_id, user.id, action)
        except LookupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        response = _response(result.run)
        if result.task_id:
            response["task_id"] = result.task_id
        return response


@router.get("/workflows/{workflow_id}/events")
async def workflow_events(
    workflow_id: str,
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
):
    last_event_id = request.headers.get("last-event-id")
    try:
        after = max(0, int(last_event_id or "0"))
    except ValueError:
        after = 0
    async with uow:
        if await uow.workflows.get_owned(workflow_id, user.id) is None:
            raise HTTPException(status_code=404, detail="workflow not found")

    async def body():
        event_factory = lambda: SqlAlchemyUnitOfWork(request.app.state.session_factory)
        async for event in iter_workflow_events(event_factory, workflow_id, after=after):
            yield encode_sse(event_id=str(event["id"]), event=str(event["event"]), data=event["data"])

    return StreamingResponse(body(), media_type="text/event-stream", headers={"cache-control": "no-cache", "x-accel-buffering": "no"})
