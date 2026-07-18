from __future__ import annotations


class RegenerateReply:
    def __init__(self, uow_factory, queue):
        self.uow_factory = uow_factory
        self.queue = queue

    async def execute(self, *, branch_id: str, parent_message_id: str, user_id: str, provider: str, model: str):
        async with self.uow_factory() as uow:
            # 同分支候选：attempt = 同 parent 已有 assistant 候选数 + 1，不 fork。
            attempt = await uow.conversations.count_assistant_siblings(branch_id, parent_message_id) + 1
            assistant = await uow.conversations.append_message(branch_id, "assistant", "", None, "PENDING", parent_message_id=parent_message_id, generation_attempt=attempt)
            await uow.commit()
        task_id = await self.queue.enqueue("proseforge.chat.generate", {"message_id": assistant.id, "parent_message_id": parent_message_id, "user_id": user_id, "provider": provider, "model": model})
        return assistant, task_id
