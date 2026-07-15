from __future__ import annotations

import pytest

from proseforge.domain.chapter.entity import Chapter
from proseforge.infrastructure.database.repositories.chapter import SqlAlchemyChapterRepository


@pytest.mark.asyncio
async def test_same_content_hash_does_not_create_second_version(session_factory):
    async with session_factory() as session:
        repository = SqlAlchemyChapterRepository(session)
        chapter = Chapter.create(project_id="p1", chapter_no=1, title="Opening")
        await repository.add(chapter)
        first = await repository.append_version(chapter_id=chapter.id, content="same")
        second = await repository.append_version(chapter_id=chapter.id, content="same")
        await session.commit()
        assert second.id == first.id
        assert second.version_no == first.version_no
