from __future__ import annotations

class CeleryTaskQueue:
    """Application port backed by Redis/Celery in production."""

    def __init__(self, client=None):
        self.client = client

    async def enqueue(self, task_name: str, payload: dict[str, object]) -> str:
        client = self.client
        if client is None:
            from proseforge.workflows.celery_app import celery
            client = celery
        result = client.send_task(task_name, args=[payload])
        return str(result.id)
