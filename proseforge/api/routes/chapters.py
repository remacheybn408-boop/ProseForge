from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.domain.chapter.entity import Chapter
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1", tags=["chapters"])


class ChapterCreateRequest(BaseModel):
    chapter_no: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)


class VersionCreateRequest(BaseModel):
    content: str = Field(min_length=0)
    base_version: int | None = Field(default=None, ge=1)


def chapter_response(chapter: Chapter) -> dict[str, object]:
    return {
        "id": chapter.id,
        "project_id": chapter.project_id,
        "chapter_no": chapter.chapter_no,
        "title": chapter.title,
        "status": chapter.status,
        "active_version_id": chapter.active_version_id,
    }


@router.post("/projects/{project_id}/chapters", status_code=status.HTTP_201_CREATED)
async def create_chapter(
    project_id: str,
    payload: ChapterCreateRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        chapter = Chapter.create(project_id=project_id, chapter_no=payload.chapter_no, title=payload.title)
        await uow.chapters.add(chapter)
        await uow.commit()
        return chapter_response(chapter)


@router.get("/projects/{project_id}/chapters")
async def list_chapters(
    project_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> list[dict[str, object]]:
    async with uow:
        if await uow.projects.get_by_id(user.id, project_id) is None:
            raise HTTPException(status_code=404, detail="project not found")
        return [chapter_response(chapter) for chapter in await uow.chapters.list_owned(project_id, user.id)]


@router.post("/chapters/{chapter_id}/versions", status_code=status.HTTP_201_CREATED)
async def append_version(
    chapter_id: str,
    payload: VersionCreateRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        chapter = await uow.chapters.get_owned(chapter_id, user.id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        if payload.base_version is not None:
            current = chapter.active_version_id
            versions = await uow.chapters.list_versions(chapter_id, user.id)
            active = next((version for version in versions if version.id == current), None)
            if active is not None and active.version_no != payload.base_version:
                raise HTTPException(status_code=409, detail={"code": "VERSION_CONFLICT", "current_version": active.version_no})
        version = await uow.chapters.append_version(chapter_id=chapter_id, content=payload.content)
        await uow.chapters.set_active_version(chapter_id, version.id)
        await uow.commit()
        return {"id": version.id, "chapter_id": version.chapter_id, "version_no": version.version_no, "content": version.content, "word_count": version.word_count}


@router.get("/chapters/{chapter_id}/versions")
async def list_versions(
    chapter_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> list[dict[str, object]]:
    async with uow:
        if await uow.chapters.get_owned(chapter_id, user.id) is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        return [
            {"id": version.id, "chapter_id": version.chapter_id, "version_no": version.version_no,
             "content": version.content, "word_count": version.word_count}
            for version in await uow.chapters.list_versions(chapter_id, user.id)
        ]
