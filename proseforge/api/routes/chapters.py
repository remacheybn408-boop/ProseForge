from __future__ import annotations

import difflib
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.application.writing.selection_action import (
    SelectionActionConflict,
    SelectionActionRequest,
    SelectionActionValidationError,
    create_selection_action_proposals,
)
from proseforge.domain.chapter.entity import Chapter
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1", tags=["chapters"])
v2_router = APIRouter(prefix="/api/v2", tags=["chapters"])


class ChapterCreateRequest(BaseModel):
    chapter_no: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=500)


class VersionCreateRequest(BaseModel):
    content: str = Field(min_length=0)
    base_version: int | None = Field(default=None, ge=1)


class SelectionActionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    action: str = Field(pattern=r"^(continue|expand|shorten|rewrite|change-tone|review)$")
    start: int = Field(alias="from", ge=0)
    end: int = Field(alias="to", ge=0)
    selected_text_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    base_version_id: str = Field(min_length=1)
    params: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range(self) -> "SelectionActionPayload":
        if self.end <= self.start:
            raise ValueError("to must be greater than from")
        return self


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


@router.post("/chapters/{chapter_id}/activate-version")
async def activate_version(
    chapter_id: str,
    version_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        if await uow.chapters.get_owned(chapter_id, user.id) is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        version = await uow.chapters.get_version_owned(chapter_id, version_id, user.id)
        if version is None:
            raise HTTPException(status_code=404, detail="version not found")
        await uow.chapters.set_active_version(chapter_id, version.id)
        await uow.commit()
        return {"chapter_id": chapter_id, "active_version_id": version.id, "version_no": version.version_no}


@router.get("/chapters/{chapter_id}/diff")
async def chapter_diff(
    chapter_id: str,
    from_version: int,
    to_version: int,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        if await uow.chapters.get_owned(chapter_id, user.id) is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        versions = await uow.chapters.list_versions(chapter_id, user.id)
    source = next((version for version in versions if version.version_no == from_version), None)
    target = next((version for version in versions if version.version_no == to_version), None)
    if source is None or target is None:
        raise HTTPException(status_code=404, detail="version not found")
    diff = list(difflib.unified_diff(source.content.splitlines(), target.content.splitlines(), fromfile=f"v{from_version}", tofile=f"v{to_version}", lineterm=""))
    return {"chapter_id": chapter_id, "from_version": from_version, "to_version": to_version, "changed": source.content != target.content, "diff": diff}


@v2_router.post("/chapters/{chapter_id}/selection-actions", status_code=status.HTTP_201_CREATED)
async def create_selection_action(
    chapter_id: str,
    payload: SelectionActionPayload,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    request = SelectionActionRequest(
        action=payload.action,  # type: ignore[arg-type]
        start=payload.start,
        end=payload.end,
        selected_text_hash=payload.selected_text_hash,
        base_version_id=payload.base_version_id,
        params=payload.params,
    )
    async with uow:
        try:
            result = await create_selection_action_proposals(
                uow=uow,
                owner_id=user.id,
                chapter_id=chapter_id,
                request=request,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except SelectionActionConflict as error:
            raise HTTPException(
                status_code=409,
                detail={"code": error.code, "current_version_id": error.current_version_id},
            ) from error
        except SelectionActionValidationError as error:
            raise HTTPException(status_code=422, detail={"code": error.code}) from error
        await uow.commit()
    if payload.action == "continue":
        return {"candidate_proposal_ids": list(result.proposal_ids)}
    return {"proposal_id": result.proposal_ids[0]}
