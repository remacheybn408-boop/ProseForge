from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable


async def iter_workflow_events(
    uow_factory: Callable[[], object],
    workflow_id: str,
    *,
    after: int = 0,
    poll_interval: float = 0.5,
) -> AsyncIterator[dict[str, object]]:
    """Replay durable workflow events and keep polling for newly committed events."""
    cursor = max(0, after)
    while True:
        async with uow_factory() as uow:
            events = await uow.workflows.events(workflow_id, cursor)
        if events:
            for event in events:
                cursor = max(cursor, int(event["id"]))
                yield event
            continue
        await asyncio.sleep(poll_interval)
