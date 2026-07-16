from __future__ import annotations

import asyncio

import pytest

from proseforge.application.workflows.event_stream import iter_workflow_events


class FakeWorkflows:
    def __init__(self) -> None:
        self.calls: list[int] = []

    async def events(self, workflow_id: str, after: int) -> list[dict[str, object]]:
        assert workflow_id == "workflow-1"
        self.calls.append(after)
        if len(self.calls) == 1:
            return [{"id": 2, "event": "RUNNING", "data": {"status": "RUNNING"}}]
        return []


class FakeUow:
    def __init__(self, workflows: FakeWorkflows) -> None:
        self.workflows = workflows

    async def __aenter__(self) -> "FakeUow":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_workflow_event_iterator_replays_then_remains_subscribed():
    workflows = FakeWorkflows()
    iterator = iter_workflow_events(lambda: FakeUow(workflows), "workflow-1", after=1, poll_interval=0.01)

    assert await anext(iterator) == {"id": 2, "event": "RUNNING", "data": {"status": "RUNNING"}}
    pending = asyncio.create_task(anext(iterator))
    await asyncio.sleep(0.02)
    assert not pending.done()
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
