from __future__ import annotations


class RegenerateReply:
    def __init__(self, uow_factory, queue):
        self.uow_factory = uow_factory
        self.queue = queue

    async def execute(self, *, branch_id: str, parent_message_id: str, user_id: str, provider: str, model: str):
        async with self.uow_factory() as uow:
            assistant = await uow.conversations.append_message(branch_id, "assistant", "", None, "PENDING", parent_message_id=parent_message_id)
            await uow.commit()
        task_id = await self.queue.enqueue("proseforge.chat.generate", {"message_id": assistant.id, "parent_message_id": parent_message_id, "user_id": user_id, "provider": provider, "model": model})
        return assistant, task_id
