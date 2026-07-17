from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.chapter import ChapterModel, ChapterVersionModel
from proseforge.infrastructure.database.models.project import ProjectModel
from proseforge.infrastructure.database.models.revision import RevisionProposalModel


class SqlAlchemyRevisionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_owned(self, proposal_id: str, owner_id: str) -> RevisionProposalModel | None:
        return await self.session.scalar(
            select(RevisionProposalModel)
            .join(ChapterModel, ChapterModel.id == RevisionProposalModel.chapter_id)
            .join(ProjectModel, ProjectModel.id == ChapterModel.project_id)
            .where(RevisionProposalModel.id == proposal_id, ProjectModel.owner_id == owner_id)
        )

    async def create(self, *, chapter_id: str, base_version_id: str, before: str, after: str, rationale: str) -> RevisionProposalModel:
        proposal = RevisionProposalModel(
            id=new_id(),
            chapter_id=chapter_id,
            base_version_id=base_version_id,
            before_hash=hashlib.sha256(before.encode("utf-8")).hexdigest(),
            after_text=after,
            after_hash=hashlib.sha256(after.encode("utf-8")).hexdigest(),
            rationale=rationale,
            status="PROPOSED",
            created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        self.session.add(proposal)
        await self.session.flush()
        return proposal

    async def current_version(self, chapter_id: str, owner_id: str) -> ChapterVersionModel | None:
        row = await self.session.scalar(
            select(ChapterVersionModel)
            .join(ChapterModel, ChapterModel.id == ChapterVersionModel.chapter_id)
            .join(ProjectModel, ProjectModel.id == ChapterModel.project_id)
            .where(
                ChapterVersionModel.chapter_id == chapter_id,
                ChapterVersionModel.id == ChapterModel.active_version_id,
                ProjectModel.owner_id == owner_id,
            )
        )
        return row
