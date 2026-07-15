from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.domain.project.entity import Project
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


class ProjectCreateRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=200, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=500)
    genre: str = ""
    style: str = ""


class ProjectResponse(BaseModel):
    id: str
    slug: str
    title: str
    genre: str
    style: str
    language: str
    status: str


class ProjectUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    genre: str | None = Field(default=None, max_length=200)
    style: str | None = Field(default=None, max_length=200)


def _response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id, slug=project.slug, title=project.title, genre=project.genre,
        style=project.style, language=project.language, status=project.status,
    )


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> ProjectResponse:
    async with uow:
        existing = await uow.projects.get_by_slug(user.id, payload.slug)
        if existing:
            raise HTTPException(status_code=409, detail="project slug already exists")
        project = Project.create(owner_id=user.id, slug=payload.slug, title=payload.title, genre=payload.genre, style=payload.style)
        await uow.projects.add(project)
        await uow.commit()
        return _response(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> list[ProjectResponse]:
    async with uow:
        return [_response(project) for project in await uow.projects.list_for_owner(user.id)]


@router.get("/{slug}", response_model=ProjectResponse)
async def get_project(
    slug: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> ProjectResponse:
    async with uow:
        project = await uow.projects.get_by_slug(user.id, slug)
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        return _response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdateRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> ProjectResponse:
    async with uow:
        project = await uow.projects.update(user.id, project_id, **payload.model_dump(exclude_unset=True))
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        await uow.commit()
        return _response(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> None:
    async with uow:
        if not await uow.projects.delete(user.id, project_id):
            raise HTTPException(status_code=404, detail="project not found")
        await uow.commit()
