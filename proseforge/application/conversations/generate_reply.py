from __future__ import annotations

import hashlib

from proseforge.providers.errors import classify_provider_error
from proseforge.application.conversations.terminal_state import terminal_message_status
from proseforge.providers.usage import normalize_provider_usage


class GenerateReply:
    def __init__(self, uow_factory, provider, event_stream=None):
        self.uow_factory = uow_factory
        self.provider = provider
        self.event_stream = event_stream

    async def _publish(self, conversation_id: str | None, message_id: str, payload: dict) -> None:
        if not self.event_stream:
            return
        await self.event_stream.publish(f"message:{message_id}", payload)
        if conversation_id:
            await self.event_stream.publish(f"conversation:{conversation_id}", payload)

    async def execute(self, *, message_id: str, request, user_id: str = "", provider: str = "unknown", model: str = "unknown"):
        chunks = 0
        call_id = f"message:{message_id}"
        async with self.uow_factory() as uow:
            count = getattr(uow.conversations, "chunk_count", None)
            if count is not None:
                chunks = await count(message_id)
        conversation_id: str | None = None
        try:
            async with self.uow_factory() as uow:
                await uow.conversations.set_message_status(message_id, "STREAMING")
                lookup = getattr(uow.conversations, "conversation_id_for_message", None)
                conversation_id = await lookup(message_id) if lookup else None
                await uow.commit()
            await self._publish(conversation_id, message_id, {"event": "message.started", "message_id": message_id})
            async for event in self.provider.stream(request):
                if event.event == "usage.updated":
                    async with self.uow_factory() as uow:
                        delta = normalize_provider_usage(provider, event.data)
                        usage_repo = getattr(uow, "usage", None)
                        if usage_repo:
                            await usage_repo.record(user_id=user_id, provider=provider, model_id=model, call_id=call_id, delta=delta, message_id=message_id, conversation_id=conversation_id)
                            await uow.commit()
                    if self.event_stream:
                        usage_payload = {"event": "usage.updated", "message_id": message_id, **delta.as_event_payload()}
                        await self._publish(conversation_id, message_id, usage_payload)
                    continue
                if event.event == "response.completed" and event.data.get("usage"):
                    async with self.uow_factory() as uow:
                        delta = normalize_provider_usage(provider, event.data, final=True)
                        usage_repo = getattr(uow, "usage", None)
                        if usage_repo:
                            await usage_repo.record(user_id=user_id, provider=provider, model_id=model, call_id=call_id, delta=delta, message_id=message_id, conversation_id=conversation_id)
                            await uow.commit()
                    if self.event_stream:
                        usage_payload = {"event": "usage.updated", "message_id": message_id, **delta.as_event_payload()}
                        await self._publish(conversation_id, message_id, usage_payload)
                    continue
                if event.event != "content.delta":
                    continue
                async with self.uow_factory() as uow:
                    status_reader = getattr(uow.conversations, "message_status", None)
                    if status_reader and await status_reader(message_id) == "CANCELLED":
                        return chunks
                    await uow.conversations.append_chunk(message_id, chunks, event.event, event.text)
                    await uow.commit()
                if self.event_stream:
                    payload = {"event": event.event, "message_id": message_id, "index": chunks, "text": event.text}
                    await self._publish(conversation_id, message_id, payload)
                chunks += 1
            content_hash = None
            async with self.uow_factory() as uow:
                status_reader = getattr(uow.conversations, "message_status", None)
                if status_reader and await status_reader(message_id) == "CANCELLED":
                    return chunks
                await uow.conversations.set_message_status(message_id, "COMPLETED")
                message_reader = getattr(uow.conversations, "get_message", None)
                message = await message_reader(message_id) if message_reader else None
                final_content = message.content if message else ""
                content_hash = hashlib.sha256(final_content.encode()).hexdigest()
                hash_writer = getattr(uow.conversations, "set_content_hash", None)
                if hash_writer:
                    await hash_writer(message_id, content_hash)
                await uow.commit()
            await self._publish(conversation_id, message_id, {"event": "message.completed", "message_id": message_id, "status": "COMPLETED", "content_hash": content_hash})
        except Exception as error:
            terminal_status = None
            async with self.uow_factory() as uow:
                status_reader = getattr(uow.conversations, "message_status", None)
                if not status_reader or await status_reader(message_id) != "CANCELLED":
                    terminal_status = terminal_message_status(chunks)
                    await uow.conversations.set_message_status(message_id, terminal_status)
                    await uow.commit()
            if terminal_status is not None:
                await self._publish(conversation_id, message_id, {"event": "message.failed", "message_id": message_id, "status": terminal_status})
            raise classify_provider_error(error) from error
        return chunks
