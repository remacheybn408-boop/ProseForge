from __future__ import annotations

import pytest

from proseforge.application.conversations.regenerate_reply import RegenerateReply
from proseforge.domain.conversation.entity import Message


class Repo:
    def __init__(self, siblings: int):
        self.siblings = siblings
        self.appended = []

    async def count_assistant_siblings(self, branch_id, parent_message_id):
        return self.siblings

    async def append_message(self, branch_id, role, content, client_request_id=None, status="COMPLETED", *, parent_message_id=None, generation_attempt=1):
        message = Message(f"m{len(self.appended)}", branch_id, role, content, status=status, parent_message_id=parent_message_id, generation_attempt=generation_attempt)
        self.appended.append(message)
        return message


class Uow:
    def __init__(self, repo): self.conversations = repo
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def commit(self): pass


class Queue:
    def __init__(self): self.enqueued = []

    async def enqueue(self, task, payload):
        self.enqueued.append((task, payload))
        return "task-1"


@pytest.mark.asyncio
async def test_regenerate_appends_sibling_with_incremented_attempt():
    repo = Repo(siblings=1)  # original assistant candidate already exists
    queue = Queue()
    message, task_id = await RegenerateReply(lambda: Uow(repo), queue).execute(branch_id="b", parent_message_id="u1", user_id="u", provider="openai", model="m")
    assert message.generation_attempt == 2
    assert message.parent_message_id == "u1"  # 同分支候选，不 fork
    assert message.branch_id == "b"
    assert message.status == "PENDING"
    assert task_id == "task-1"
    assert queue.enqueued[0][1]["message_id"] == message.id


@pytest.mark.asyncio
async def test_regenerate_third_candidate_gets_attempt_three():
    repo = Repo(siblings=2)
    message, _ = await RegenerateReply(lambda: Uow(repo), Queue()).execute(branch_id="b", parent_message_id="u1", user_id="u", provider="openai", model="m")
    assert message.generation_attempt == 3
