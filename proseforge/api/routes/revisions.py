from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.infrastructure.database.models.revision import RevisionProposalModel
from sqlalchemy import select

router = APIRouter(prefix="/api/v2", tags=["reviews-revisions"])


class ProposalRequest(BaseModel):
    base_version_id: str = Field(min_length=1)
    after_text: str
    rationale: str = Field(min_length=1, max_length=4000)


def _response(row) -> dict[str, object]:
    return {
        "id": row.id,
        "chapter_id": row.chapter_id,
        "base_version_id": row.base_version_id,
        "before_hash": row.before_hash,
        "after_hash": row.after_hash,
        "after_text": row.after_text,
        "rationale": row.rationale,
        "status": row.status,
    }


@router.post("/chapters/{chapter_id}/proposals", status_code=status.HTTP_201_CREATED)
async def create_proposal(
    chapter_id: str,
    payload: ProposalRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        chapter = await uow.chapters.get_owned(chapter_id, user.id)
        if chapter is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        base = await uow.chapters.get_version_owned(chapter_id, payload.base_version_id, user.id)
        if base is None:
            raise HTTPException(status_code=404, detail="base version not found")
        row = await uow.revisions.create(
            chapter_id=chapter_id,
            base_version_id=base.id,
            before=base.content,
            after=payload.after_text,
            rationale=payload.rationale,
        )
        await uow.commit()
        return _response(row)


@router.get("/chapters/{chapter_id}/proposals")
async def list_proposals(
    chapter_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> list[dict[str, object]]:
    async with uow:
        if await uow.chapters.get_owned(chapter_id, user.id) is None:
            raise HTTPException(status_code=404, detail="chapter not found")
        rows = await uow.session.scalars(select(RevisionProposalModel).where(RevisionProposalModel.chapter_id == chapter_id))
        return [_response(row) for row in rows]


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        row = await uow.revisions.get_owned(proposal_id, user.id)
        if row is None:
            raise HTTPException(status_code=404, detail="proposal not found")
        if row.status == "PROPOSED":
            row.status = "REJECTED"
            await uow.commit()
        return _response(row)


@router.post("/proposals/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, object]:
    async with uow:
        row = await uow.revisions.get_owned(proposal_id, user.id)
        if row is None:
            raise HTTPException(status_code=404, detail="proposal not found")
        if row.status == "APPROVED":
            return _response(row)
        if row.status != "PROPOSED":
            raise HTTPException(status_code=409, detail="proposal is not approvable")
        current = await uow.revisions.current_version(row.chapter_id, user.id)
        if current is None or current.id != row.base_version_id or current.content_hash != row.before_hash:
            raise HTTPException(status_code=409, detail={"code": "STALE_PROPOSAL", "current_version_id": current.id if current else None})
        version = await uow.chapters.append_version(chapter_id=row.chapter_id, content=row.after_text)
        await uow.chapters.set_active_version(row.chapter_id, version.id)
        row.status = "APPROVED"
        await uow.commit()
        return {**_response(row), "version": {"id": version.id, "version_no": version.version_no, "content": version.content}}
