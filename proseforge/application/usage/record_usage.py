from __future__ import annotations


class UsageRecorder:
    def __init__(self, uow):
        self.uow = uow

    async def record(self, **kwargs):
        return await self.uow.usage.record(**kwargs)
