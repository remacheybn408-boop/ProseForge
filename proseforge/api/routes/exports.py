from __future__ import annotations

import hashlib
import json
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.application.writing.export_service import render_docx, render_epub
from proseforge.infrastructure.database.models.chapter import ChapterModel, ChapterVersionModel
from proseforge.infrastructure.database.models.project import ProjectModel
from pydantic import BaseModel, Field
from sqlalchemy import select

router = APIRouter(prefix="/api/v1", tags=["exports"])


class ExportRequest(BaseModel):
    format: str = Field(pattern=r"^(txt|md|json|docx|epub)$")
    version_ids: list[str] = Field(default_factory=list, max_length=200)
    title: str | None = Field(default=None, max_length=500)
    author: str | None = Field(default=None, max_length=200)
    locale: str = "en"


async def _snapshot(uow: SqlAlchemyUnitOfWork, project_id: str, owner_id: str, version_ids: list[str]):
    query = (
        select(ChapterModel, ChapterVersionModel)
        .join(ProjectModel, ProjectModel.id == ChapterModel.project_id)
        .join(ChapterVersionModel, ChapterVersionModel.chapter_id == ChapterModel.id)
        .where(ProjectModel.id == project_id, ProjectModel.owner_id == owner_id, ChapterVersionModel.id.in_(version_ids))
        .order_by(ChapterModel.chapter_no, ChapterVersionModel.version_no)
    )
    rows = (await uow.session.execute(query)).all()
    if len(rows) != len(set(version_ids)):
        raise HTTPException(status_code=404, detail="one or more versions not found")
    chapters = [(uow.chapters._chapter(chapter), version.content) for chapter, version in rows]
    manifest = {
        "project_id": project_id,
        "version_ids": [version.id for _, version in rows],
        "content_hashes": {version.id: hashlib.sha256(version.content.encode("utf-8")).hexdigest() for _, version in rows},
    }
    return chapters, manifest


@router.get("/projects/{project_id}/exports/{format_name}")
async def export_project(
    project_id: str,
    format_name: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
    version_ids: str | None = None,
) -> Response:
    format_name = format_name.lower()
    if format_name not in {"txt", "md", "json", "docx", "epub"}:
        raise HTTPException(status_code=400, detail="unsupported export format")
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        selected = [item for item in (version_ids or "").split(",") if item]
        if selected:
            chapters, manifest = await _snapshot(uow, project_id, user.id, selected)
        else:
            chapters = await uow.chapters.active_contents(project_id, user.id)
            manifest = {"project_id": project_id, "version_ids": [], "content_hashes": {}, "warning": "legacy active fallback"}
    if format_name == "docx":
        return Response(content=render_docx(chapters), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"content-disposition": f'attachment; filename="proseforge-{project_id}.docx"', "x-proseforge-manifest": json.dumps(manifest, separators=(",", ":"))})
    if format_name == "epub":
        return Response(content=render_epub(f"ProseForge {project_id}", chapters), media_type="application/epub+zip", headers={"content-disposition": f'attachment; filename="proseforge-{project_id}.epub"', "x-proseforge-manifest": json.dumps(manifest, separators=(",", ":"))})
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
        headers={"content-disposition": f'attachment; filename="proseforge-{project_id}.{format_name}"', "x-proseforge-manifest": json.dumps(manifest, separators=(",", ":"))},
    )


@router.post("/projects/{project_id}/exports", status_code=status.HTTP_202_ACCEPTED)
async def request_export(
    project_id: str,
    payload: ExportRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
    query = urlencode({"version_ids": ",".join(payload.version_ids)}) if payload.version_ids else ""
    return {"status": "READY", "format": payload.format, "version_ids": payload.version_ids, "download_url": f"/api/v1/projects/{project_id}/exports/{payload.format}{'?' + query if query else ''}"}
