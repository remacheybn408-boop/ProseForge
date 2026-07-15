from __future__ import annotations


class SendMessage:
    def __init__(self, uow_factory, queue):
        self.uow_factory = uow_factory
        self.queue = queue

    async def execute(self, *, branch_id: str, content: str, client_request_id: str, user_id: str = "", provider: str = "openai", model: str = "gpt-4.1-mini"):
        async with self.uow_factory() as uow:
            user = await uow.conversations.append_message(branch_id, "user", content, client_request_id, "COMPLETED")
            assistant = await uow.conversations.append_message(branch_id, "assistant", "", None, "PENDING")
            await uow.commit()
        task_id = await self.queue.enqueue("proseforge.chat.generate", {"message_id": assistant.id, "user_message_id": user.id, "user_id": user_id, "provider": provider, "model": model})
        return user, assistant, task_id
