from typing import Protocol


class TaskQueue(Protocol):
    async def enqueue(self, task_name: str, payload: dict[str, object]) -> str: ...


class TaskLease(Protocol):
    async def release(self) -> None: ...
