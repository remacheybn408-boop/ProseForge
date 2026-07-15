from __future__ import annotations


class GenerateReply:
    def __init__(self, uow_factory, provider, event_stream=None):
        self.uow_factory = uow_factory
        self.provider = provider
        self.event_stream = event_stream

    async def execute(self, *, message_id: str, request):
        chunks = 0
        try:
            async with self.uow_factory() as uow:
                await uow.conversations.set_message_status(message_id, "STREAMING")
                await uow.commit()
            async for event in self.provider.stream(request):
                if event.event != "content.delta":
                    continue
                async with self.uow_factory() as uow:
                    await uow.conversations.append_chunk(message_id, chunks, event.event, event.text)
                    await uow.commit()
                if self.event_stream:
                    await self.event_stream.publish(f"message:{message_id}", {"index": chunks, "text": event.text})
                chunks += 1
            async with self.uow_factory() as uow:
                await uow.conversations.set_message_status(message_id, "COMPLETED")
                await uow.commit()
        except Exception:
            async with self.uow_factory() as uow:
                await uow.conversations.set_message_status(message_id, "PARTIAL")
                await uow.commit()
            raise
        return chunks
