from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1", tags=["exports"])


@router.get("/projects/{project_id}/exports/{format_name}")
async def export_project(
    project_id: str,
    format_name: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> Response:
    format_name = format_name.lower()
    if format_name not in {"txt", "md", "json"}:
        raise HTTPException(status_code=501, detail="export format is not available yet")
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        chapters = await uow.chapters.active_contents(project_id, user.id)
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
