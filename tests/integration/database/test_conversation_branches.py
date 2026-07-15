import pytest

from proseforge.domain.conversation.entity import Conversation
from proseforge.infrastructure.database.repositories.conversation import SqlAlchemyConversationRepository


@pytest.mark.asyncio
async def test_branch_inherits_only_to_fork_point(session_factory):
    async with session_factory() as session:
        repository = SqlAlchemyConversationRepository(session)
        root = Conversation.create("p1", "Draft")
        main = await repository.create(root)
        first = await repository.append_message(main.id, "user", "one")
        second = await repository.append_message(main.id, "assistant", "two")
        await repository.append_message(main.id, "user", "three")
        branch = await repository.fork(root.id, second.id, "Alternative")
        visible = await repository.list_visible_messages(branch.id)
        assert [item.id for item in visible] == [first.id, second.id]
