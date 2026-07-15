import pytest

from proseforge.application.conversations.generate_reply import GenerateReply
from proseforge.domain.ports.model_provider import GenerationEvent


class Provider:
    async def stream(self, request):
        yield GenerationEvent("content.delta", "one")
        yield GenerationEvent("content.delta", "two")
        raise RuntimeError("network interruption")


class Repo:
    def __init__(self):
        self.statuses = []
        self.chunks = []

    async def set_message_status(self, message_id, status):
        self.statuses.append(status)

    async def append_chunk(self, *args):
        self.chunks.append(args)
    async def chunk_count(self, message_id): return 2


class Uow:
    def __init__(self, repo): self.conversations = repo
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def commit(self): pass


@pytest.mark.asyncio
async def test_interrupted_stream_marks_partial_after_persisting_chunks():
    repo = Repo()
    with pytest.raises(RuntimeError):
        await GenerateReply(lambda: Uow(repo), Provider()).execute(message_id="m", request=object())
    assert repo.chunks == [("m", 2, "content.delta", "one"), ("m", 3, "content.delta", "two")]
    assert repo.statuses[-1] == "PARTIAL"
