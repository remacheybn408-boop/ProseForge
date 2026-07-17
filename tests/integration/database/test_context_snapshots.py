from __future__ import annotations

import pytest

from proseforge.domain.project.entity import Project
from proseforge.infrastructure.database.repositories.context import SqlAlchemyContextRepository
from proseforge.infrastructure.database.repositories.project import SqlAlchemyProjectRepository


@pytest.mark.asyncio
async def test_context_snapshot_is_durable_and_owner_scoped(session_factory):
    async with session_factory() as session:
        project = Project.create(owner_id="snapshot-owner", slug="snapshot-book", title="Snapshot book")
        await SqlAlchemyProjectRepository(session).add(project)
        repository = SqlAlchemyContextRepository(session)
        item = await repository.add(project.id, "manual", "A durable story fact")
        snapshot = await repository.snapshot(project.id, [item])
        await session.commit()

    async with session_factory() as session:
        repository = SqlAlchemyContextRepository(session)
        found = await repository.get_snapshot_owned(snapshot.id, "snapshot-owner")
        assert found is not None
        assert await repository.get_snapshot_owned(snapshot.id, "other-owner") is None


@pytest.mark.asyncio
async def test_context_snapshot_restores_source_without_deleting_new_memories(session_factory):
    async with session_factory() as session:
        project = Project.create(owner_id="restore-owner", slug="restore-book", title="Restore book")
        await SqlAlchemyProjectRepository(session).add(project)
        repository = SqlAlchemyContextRepository(session)
        original = await repository.add(project.id, "manual", "Original lighthouse fact")
        original.pinned = True
        original.priority = 80
        original.excluded = True
        snapshot = await repository.snapshot(project.id, [original])
        original.content = "Changed after snapshot"
        await repository.add(project.id, "manual", "New memory after snapshot")

        restored = await repository.restore_snapshot(project.id, snapshot)
        await session.commit()

    assert [item.content for item in restored] == ["Original lighthouse fact", "New memory after snapshot"]
    assert restored[0].pinned is True
    assert restored[0].priority == 80
    assert restored[0].excluded is True
