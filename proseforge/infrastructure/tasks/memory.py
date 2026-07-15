from __future__ import annotations


class InMemoryTaskQueue:
    def __init__(self):
        self.tasks: list[tuple[str, dict[str, object]]] = []

    async def enqueue(self, task_name: str, payload: dict[str, object]) -> str:
        self.tasks.append((task_name, payload))
        return f"task-{len(self.tasks)}"
