from __future__ import annotations

from proseforge.providers.errors import classify_provider_error


class GenerateReply:
    def __init__(self, uow_factory, provider, event_stream=None):
        self.uow_factory = uow_factory
        self.provider = provider
        self.event_stream = event_stream

    async def execute(self, *, message_id: str, request):
        chunks = 0
        async with self.uow_factory() as uow:
            count = getattr(uow.conversations, "chunk_count", None)
            if count is not None:
                chunks = await count(message_id)
        try:
            async with self.uow_factory() as uow:
                await uow.conversations.set_message_status(message_id, "STREAMING")
                await uow.commit()
            async for event in self.provider.stream(request):
                if event.event != "content.delta":
                    continue
                async with self.uow_factory() as uow:
                    await uow.conversations.append_chunk(message_id, chunks, event.event, event.text)
                    lookup = getattr(uow.conversations, "conversation_id_for_message", None)
                    conversation_id = await lookup(message_id) if lookup else None
                    await uow.commit()
                if self.event_stream:
                    payload = {"event": event.event, "message_id": message_id, "index": chunks, "text": event.text}
                    await self.event_stream.publish(f"message:{message_id}", payload)
                    if conversation_id:
                        await self.event_stream.publish(f"conversation:{conversation_id}", payload)
                chunks += 1
            async with self.uow_factory() as uow:
                await uow.conversations.set_message_status(message_id, "COMPLETED")
                await uow.commit()
        except Exception as error:
            async with self.uow_factory() as uow:
                await uow.conversations.set_message_status(message_id, "PARTIAL")
                await uow.commit()
            raise classify_provider_error(error) from error
        return chunks
