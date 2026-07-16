from typing import AsyncIterator, Protocol


class EventStream(Protocol):
    async def publish(self, topic: str, event: dict[str, object]) -> None: ...

    async def subscribe(self, topic: str, after_id: str | None = None) -> AsyncIterator[dict[str, object]]: ...
