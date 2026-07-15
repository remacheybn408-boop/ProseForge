import pytest

from proseforge.infrastructure.database.models.project import ProjectModel
from proseforge.infrastructure.database.repositories.workflow import SqlAlchemyWorkflowRepository


@pytest.mark.asyncio
async def test_workflow_events_and_transitions_are_durable(session_factory):
    async with session_factory() as session:
        session.add(ProjectModel(id="p-workflow", owner_id="u1", slug="workflow", title="Workflow"))
        await session.flush()
        repository = SqlAlchemyWorkflowRepository(session)
        run = await repository.create("p-workflow", "NOVEL")
        await repository.transition(run, "RUNNING")
        await session.commit()

    async with session_factory() as session:
        repository = SqlAlchemyWorkflowRepository(session)
        owned = await repository.get_owned(run.id, "u1")
        events = await repository.events(run.id)

    assert owned is not None and owned.status == "RUNNING"
    assert [event["event"] for event in events] == ["QUEUED", "RUNNING"]
