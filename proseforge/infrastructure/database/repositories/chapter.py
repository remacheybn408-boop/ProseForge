from __future__ import annotations

import hashlib

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.chapter.entity import Chapter, ChapterVersion
from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.chapter import ChapterModel, ChapterVersionModel


class SqlAlchemyChapterRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, chapter: Chapter) -> Chapter:
        self.session.add(ChapterModel(**chapter.__dict__))
        return chapter

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
