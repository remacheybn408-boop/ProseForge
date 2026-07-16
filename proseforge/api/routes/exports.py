from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.application.writing.export_service import render_docx, render_epub
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1", tags=["exports"])


class ExportRequest(BaseModel):
    format: str = Field(pattern=r"^(txt|md|json|docx|epub)$")


@router.get("/projects/{project_id}/exports/{format_name}")
async def export_project(
    project_id: str,
    format_name: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> Response:
    format_name = format_name.lower()
    if format_name not in {"txt", "md", "json", "docx", "epub"}:
        raise HTTPException(status_code=400, detail="unsupported export format")
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        chapters = await uow.chapters.active_contents(project_id, user.id)
    if format_name == "docx":
        return Response(content=render_docx(chapters), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"content-disposition": f'attachment; filename="proseforge-{project_id}.docx"'})
    if format_name == "epub":
        return Response(content=render_epub(f"ProseForge {project_id}", chapters), media_type="application/epub+zip", headers={"content-disposition": f'attachment; filename="proseforge-{project_id}.epub"'})
    if format_name == "json":
        body = json.dumps(
            [{"chapter_no": chapter.chapter_no, "title": chapter.title, "content": content} for chapter, content in chapters],
            ensure_ascii=False,
            indent=2,
        )
        media_type = "application/json"
    elif format_name == "md":
        body = "\n\n".join(f"# {chapter.title}\n\n{content}" for chapter, content in chapters)
        media_type = "text/markdown; charset=utf-8"
    else:
        body = "\n\n".join(f"{chapter.title}\n\n{content}" for chapter, content in chapters)
        media_type = "text/plain; charset=utf-8"
    return Response(
        content=body,
        media_type=media_type,
        headers={"content-disposition": f'attachment; filename="proseforge-{project_id}.{format_name}"'},
    )


@router.post("/projects/{project_id}/exports", status_code=status.HTTP_202_ACCEPTED)
async def request_export(
    project_id: str,
    payload: ExportRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, str]:
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
    return {"status": "READY", "format": payload.format, "download_url": f"/api/v1/projects/{project_id}/exports/{payload.format}"}
