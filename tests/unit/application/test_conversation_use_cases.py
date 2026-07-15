import pytest

from proseforge.application.conversations.send_message import SendMessage


class Repo:
    def __init__(self):
        self.calls = []

    async def append_message(self, *args):
        self.calls.append(args)
        return type("Message", (), {"id": str(len(self.calls))})()


class Uow:
    def __init__(self, repo): self.conversations = repo
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def commit(self): pass


class Queue:
    def __init__(self): self.enqueued = []
    async def enqueue(self, name, payload): self.enqueued.append((name, payload)); return "task-1"


@pytest.mark.asyncio
async def test_send_message_commits_user_and_pending_assistant_before_queueing():
    repo, queue = Repo(), Queue()
    result = await SendMessage(lambda: Uow(repo), queue).execute(branch_id="b", content="hello", client_request_id="req-1")
    assert [call[1] for call in repo.calls] == ["user", "assistant"]
    assert repo.calls[0][3:] == ("req-1", "COMPLETED")
    assert repo.calls[1][3:] == (None, "PENDING")
    assert result[2] == "task-1"
