from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.chapter.entity import Chapter, ChapterVersion
from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.chapter import ChapterModel, ChapterVersionModel
from proseforge.infrastructure.database.models.project import ProjectModel


class SqlAlchemyChapterRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, chapter: Chapter) -> Chapter:
        self.session.add(ChapterModel(**chapter.__dict__))
        return chapter

    async def list_owned(self, project_id: str, owner_id: str) -> list[Chapter]:
        rows = await self.session.scalars(
            select(ChapterModel)
            .join(ProjectModel, ProjectModel.id == ChapterModel.project_id)
            .where(ChapterModel.project_id == project_id, ProjectModel.owner_id == owner_id)
            .order_by(ChapterModel.chapter_no)
        )
        return [self._chapter(row) for row in rows]

    async def get_owned(self, chapter_id: str, owner_id: str) -> Chapter | None:
        row = await self.session.scalar(
            select(ChapterModel)
            .join(ProjectModel, ProjectModel.id == ChapterModel.project_id)
            .where(ChapterModel.id == chapter_id, ProjectModel.owner_id == owner_id)
        )
        return None if row is None else self._chapter(row)

    async def append_version(self, *, chapter_id: str, content: str) -> ChapterVersion:
        content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        existing = await self.session.execute(
            select(ChapterVersionModel).where(
                ChapterVersionModel.chapter_id == chapter_id,
                ChapterVersionModel.content_hash == content_hash,
            )
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return self._to_domain(row)

        maximum = await self.session.scalar(
            select(func.max(ChapterVersionModel.version_no)).where(ChapterVersionModel.chapter_id == chapter_id)
        )
        row = ChapterVersionModel(
            id=new_id(),
            chapter_id=chapter_id,
            version_no=(maximum or 0) + 1,
            content=content,
            content_hash=content_hash,
            word_count=len(content),
        )
        self.session.add(row)
        await self.session.flush()
        return self._to_domain(row)

    async def set_active_version(self, chapter_id: str, version_id: str) -> None:
        row = await self.session.get(ChapterModel, chapter_id)
        if row is None:
            raise ValueError("chapter does not exist")
        row.active_version_id = version_id
        row.status = "DRAFTED"
        await self.session.flush()

    @staticmethod
    def _chapter(row: ChapterModel) -> Chapter:
        return Chapter(
            id=row.id,
            project_id=row.project_id,
            chapter_no=row.chapter_no,
            title=row.title,
            status=row.status,
            active_version_id=row.active_version_id,
        )

    @staticmethod
    def _to_domain(row: ChapterVersionModel) -> ChapterVersion:
        return ChapterVersion(
            id=row.id,
            chapter_id=row.chapter_id,
            version_no=row.version_no,
            content=row.content,
            content_hash=row.content_hash,
            word_count=row.word_count,
        )
