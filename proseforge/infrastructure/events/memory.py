from __future__ import annotations

from collections.abc import AsyncIterator


class InMemoryEventStream:
    def __init__(self):
        self._events: dict[str, list[dict[str, object]]] = {}

    async def publish(self, topic: str, event: dict[str, object]) -> None:
        events = self._events.setdefault(topic, [])
        events.append({"id": str(len(events) + 1), **event})

    async def subscribe(self, topic: str, after_id: str | None = None) -> AsyncIterator[dict[str, object]]:
        events = self._events.get(topic, [])
        threshold = int(after_id or "0")
        for event in events:
            if int(str(event["id"])) > threshold:
                yield event
