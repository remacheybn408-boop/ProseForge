class RecoverPartial:
    def __init__(self, uow_factory, queue):
        self.uow_factory = uow_factory
        self.queue = queue

    async def execute(self, *, message_id: str):
        task_id = await self.queue.enqueue("proseforge.chat.generate", {"message_id": message_id, "resume": True})
        return task_id
