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


@pytest.mark.asyncio
async def test_duplicate_client_request_reuses_existing_assistant(session_factory):
    async with session_factory() as session:
        repository = SqlAlchemyConversationRepository(session)
        branch = await repository.create(Conversation.create("p-idempotent"))
        user = await repository.append_message(branch.id, "user", "hello", "client-1")
        assistant = await repository.append_message(branch.id, "assistant", "", None, "PENDING")
        duplicate = await repository.get_by_client_request_id("client-1")
        reused = await repository.assistant_after(duplicate.id)
        assert duplicate is not None and duplicate.id == user.id
        assert reused is not None and reused.id == assistant.id
