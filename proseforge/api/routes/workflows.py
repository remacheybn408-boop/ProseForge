from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.api.sse.encoder import encode_sse
from proseforge.application.auth.service import AuthUser
from proseforge.domain.chapter.entity import Chapter
from proseforge.domain.workflow.state import ALLOWED_TRANSITIONS
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1", tags=["workflows"])


class NovelWorkflowRequest(BaseModel):
    chapter_numbers: list[int] = Field(default_factory=list, min_length=1)


def _response(run) -> dict[str, str]:
    return {"id": run.id, "project_id": run.project_id, "workflow_type": run.workflow_type, "status": run.status}


@router.post("/projects/{project_id}/workflows/novel", status_code=status.HTTP_201_CREATED)
async def create_workflow(
    project_id: str,
    payload: NovelWorkflowRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, str]:
    async with uow:
        project = await uow.projects.get_by_id(user.id, project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        existing = {chapter.chapter_no for chapter in await uow.chapters.list_owned(project.id, user.id)}
        for chapter_no in payload.chapter_numbers:
            if chapter_no not in existing:
                await uow.chapters.add(Chapter.create(project_id=project.id, chapter_no=chapter_no, title=f"Chapter {chapter_no}"))
        return_value = await uow.workflows.create(project.id, "NOVEL")
        await uow.commit()
        return _response(return_value)


@router.get("/workflows/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, str]:
    async with uow:
        run = await uow.workflows.get_owned(workflow_id, user.id)
        if run is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        return _response(run)


@router.post("/workflows/{workflow_id}/{action}")
async def control_workflow(
    workflow_id: str,
    action: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, str]:
    targets = {"pause": "PAUSED", "resume": "RUNNING", "cancel": "CANCELLED", "retry": "RETRYING"}
    target = targets.get(action)
    if target is None:
        raise HTTPException(status_code=404, detail="workflow action not found")
    async with uow:
        run = await uow.workflows.get_owned(workflow_id, user.id)
        if run is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        if target not in ALLOWED_TRANSITIONS.get(run.status, set()):
            raise HTTPException(status_code=409, detail=f"invalid workflow transition: {run.status} -> {target}")
        await uow.workflows.transition(run, target)
        await uow.commit()
        return _response(run)


@router.get("/workflows/{workflow_id}/events")
async def workflow_events(
    workflow_id: str,
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
):
    del request
    async with uow:
        if await uow.workflows.get_owned(workflow_id, user.id) is None:
            raise HTTPException(status_code=404, detail="workflow not found")
        events = await uow.workflows.events(workflow_id, 0)

    async def body():
        for event in events:
            yield encode_sse(event_id=str(event["id"]), event=str(event["event"]), data=event["data"])

    return StreamingResponse(body(), media_type="text/event-stream", headers={"cache-control": "no-cache", "x-accel-buffering": "no"})
