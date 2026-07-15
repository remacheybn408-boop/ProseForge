import pytest

from proseforge.domain.conversation.entity import Conversation
from proseforge.infrastructure.database.repositories.conversation import SqlAlchemyConversationRepository


@pytest.mark.asyncio
async def test_duplicate_chunk_is_idempotent(session_factory):
    async with session_factory() as session:
        repository = SqlAlchemyConversationRepository(session)
        branch = await repository.create(Conversation.create("p1"))
        message = await repository.append_message(branch.id, "assistant", "stream")
        first = await repository.append_chunk(message.id, 0, "content.delta", "hel")
        second = await repository.append_chunk(message.id, 0, "content.delta", "hel")
        assert second.id == first.id
