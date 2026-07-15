from __future__ import annotations

import json
from collections.abc import AsyncIterator

from sqlalchemy import func, select

from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.conversation import ConversationEventModel


class DatabaseEventStream:
    """Durable event log used by SSE reconnects.

    The topic suffix is stored as the stream key so message and conversation
    streams can share one append-only table without leaking transport details
    into the domain models.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def publish(self, topic: str, event: dict[str, object]) -> None:
        stream_key = topic.split(":", 1)[-1]
        async with self.session_factory() as session:
            next_sequence = await session.scalar(
                select(func.coalesce(func.max(ConversationEventModel.event_sequence), 0)).where(
                    ConversationEventModel.conversation_id == stream_key
                )
            )
            sequence = int(next_sequence or 0) + 1
            session.add(
                ConversationEventModel(
                    id=new_id(),
                    conversation_id=stream_key,
                    event_sequence=sequence,
                    event_type=str(event.get("event", "message")),
                    payload=json.dumps(event, ensure_ascii=False),
                )
            )
            await session.commit()

    async def subscribe(self, topic: str, after_id: str | None = None) -> AsyncIterator[dict[str, object]]:
        stream_key = topic.split(":", 1)[-1]
        threshold = int(after_id or "0")
        async with self.session_factory() as session:
            rows = await session.scalars(
                select(ConversationEventModel)
                .where(
                    ConversationEventModel.conversation_id == stream_key,
                    ConversationEventModel.event_sequence > threshold,
                )
                .order_by(ConversationEventModel.event_sequence)
            )
            for row in rows:
                payload = json.loads(row.payload)
                yield {"id": str(row.event_sequence), "event": row.event_type, **payload}
