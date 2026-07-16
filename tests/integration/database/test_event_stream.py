import pytest

from proseforge.infrastructure.events.database import DatabaseEventStream


@pytest.mark.asyncio
async def test_database_event_stream_replays_after_last_event(session_factory):
    stream = DatabaseEventStream(session_factory)
    await stream.publish("conversation:c1", {"event": "content.delta", "text": "one"})
    await stream.publish("conversation:c1", {"event": "content.delta", "text": "two"})

    events = [event async for event in stream.subscribe("conversation:c1", "1")]

    assert [(event["id"], event["text"]) for event in events] == [("2", "two")]


@pytest.mark.asyncio
async def test_database_event_stream_allocates_unique_ids_for_concurrent_publishers(session_factory):
    import asyncio

    stream = DatabaseEventStream(session_factory)
    await asyncio.gather(
        stream.publish("conversation:concurrent", {"event": "content.delta", "text": "one"}),
        stream.publish("conversation:concurrent", {"event": "content.delta", "text": "two"}),
    )

    events = [event async for event in stream.subscribe("conversation:concurrent")]

    assert [event["id"] for event in events] == ["1", "2"]
