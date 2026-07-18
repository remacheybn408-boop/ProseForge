from __future__ import annotations


class SendMessage:
    def __init__(self, uow_factory, queue):
        self.uow_factory = uow_factory
        self.queue = queue

    async def execute(self, *, branch_id: str, content: str, client_request_id: str, user_id: str = "", provider: str = "openai", model: str = "gpt-4.1-mini", reasoning_level: str = "auto"):
        async with self.uow_factory() as uow:
            lock = getattr(uow.conversations, "lock_client_request", None)
            if lock is not None:
                await lock(client_request_id)
            lookup = getattr(uow.conversations, "get_by_client_request_id", None)
            existing = await lookup(client_request_id) if lookup is not None else None
            if existing is not None:
                assistant_lookup = getattr(uow.conversations, "assistant_after", None)
                assistant = await assistant_lookup(existing.id) if assistant_lookup is not None else None
                if assistant is not None:
                    return existing, assistant, "deduplicated"
            user = await uow.conversations.append_message(branch_id, "user", content, client_request_id, "COMPLETED")
            assistant = await uow.conversations.append_message(branch_id, "assistant", "", None, "PENDING")
            await uow.commit()
        task_id = await self.queue.enqueue("proseforge.chat.generate", {"message_id": assistant.id, "user_message_id": user.id, "user_id": user_id, "provider": provider, "model": model, "reasoning_level": reasoning_level})
        return user, assistant, task_id
