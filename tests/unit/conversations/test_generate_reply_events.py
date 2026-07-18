from __future__ import annotations

import hashlib

import pytest

from proseforge.application.conversations.generate_reply import GenerateReply
from proseforge.domain.conversation.entity import Message
from proseforge.domain.ports.model_provider import GenerationEvent


class Repo:
    def __init__(self):
        self.statuses = []
        self.chunks = []
        self.hashes = []
        self.content = ""

    async def set_message_status(self, message_id, status):
        self.statuses.append(status)

    async def append_chunk(self, message_id, index, event_type, text):
        self.chunks.append((message_id, index, event_type, text))
        self.content += text

    async def chunk_count(self, message_id):
        return len(self.chunks)

    async def conversation_id_for_message(self, message_id):
        return "conv-1"

    async def get_message(self, message_id):
        return Message(id=message_id, branch_id="b1", role="assistant", content=self.content)

    async def set_content_hash(self, message_id, content_hash):
        self.hashes.append(content_hash)


class Uow:
    def __init__(self, repo):
        self.conversations = repo

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def commit(self):
        return None


class EventStream:
    def __init__(self):
        self.events = []

    async def publish(self, topic, payload):
        self.events.append((topic, payload))


class TwoChunkProvider:
    async def stream(self, request):
        yield GenerationEvent("content.delta", "one")
        yield GenerationEvent("content.delta", "two")


class UsageRepo:
    def __init__(self):
        self.records = []

    async def record(self, **kwargs):
        self.records.append(kwargs)


class UsageUow(Uow):
    def __init__(self, repo, usage):
        super().__init__(repo)
        self.usage = usage


class FailingProvider:
    async def stream(self, request):
        yield GenerationEvent("content.delta", "one")
        raise RuntimeError("network interruption")


@pytest.mark.asyncio
async def test_started_and_completed_events_wrap_the_stream():
    repo, events = Repo(), EventStream()
    await GenerateReply(lambda: Uow(repo), TwoChunkProvider(), events).execute(message_id="m1", request=object())
    names = [payload["event"] for _, payload in events.events]
    assert names[0] == "message.started"
    assert names[-1] == "message.completed"
    # 两个 delta 各自发到 message 与 conversation 两个 topic（既有行为不回归）
    delta_topics = [topic for topic, payload in events.events if payload["event"] == "content.delta"]
    assert delta_topics == ["message:m1", "conversation:conv-1", "message:m1", "conversation:conv-1"]
    # started must be published before the first delta
    assert names.index("message.started") < names.index("content.delta")
    # both message and conversation topics receive the lifecycle events
    started_topics = {topic for topic, payload in events.events if payload["event"] == "message.started"}
    assert started_topics == {"message:m1", "conversation:conv-1"}
    completed = [payload for _, payload in events.events if payload["event"] == "message.completed"][0]
    assert completed["content_hash"] == hashlib.sha256("onetwo".encode()).hexdigest()
    assert repo.hashes == [hashlib.sha256("onetwo".encode()).hexdigest()]


@pytest.mark.asyncio
async def test_failed_event_is_published_after_terminal_status():
    repo, events = Repo(), EventStream()
    with pytest.raises(RuntimeError):
        await GenerateReply(lambda: Uow(repo), FailingProvider(), events).execute(message_id="m1", request=object())
    names = [payload["event"] for _, payload in events.events]
    assert names[0] == "message.started"
    assert names[-1] == "message.failed"
    failed = [payload for _, payload in events.events if payload["event"] == "message.failed"][0]
    assert failed["status"] == "PARTIAL"
    assert repo.statuses[-1] == "PARTIAL"


@pytest.mark.asyncio
async def test_completion_without_provider_usage_records_missing_source():
    repo, events, usage = Repo(), EventStream(), UsageRepo()
    await GenerateReply(lambda: UsageUow(repo, usage), TwoChunkProvider(), events).execute(message_id="m1", request=object())
    # provider 全程未回 usage → 落一条 source="missing" 的记录，绝不假装是 provider 值
    assert len(usage.records) == 1
    delta = usage.records[0]["delta"]
    assert delta.source == "missing"
    assert delta.final is True
    usage_events = [payload for _, payload in events.events if payload["event"] == "usage.updated"]
    assert [payload["source"] for payload in usage_events] == ["missing", "missing"]  # message + conversation 双 topic（既有发布模式）


@pytest.mark.asyncio
async def test_provider_usage_is_not_overwritten_with_missing():
    class UsageProvider:
        async def stream(self, request):
            yield GenerationEvent("content.delta", "one")
            yield GenerationEvent("usage.updated", data={"usage": {"input_tokens": 3, "output_tokens": 4}})

    repo, events, usage = Repo(), EventStream(), UsageRepo()
    await GenerateReply(lambda: UsageUow(repo, usage), UsageProvider(), events).execute(message_id="m1", request=object())
    assert [record["delta"].source for record in usage.records] == ["provider"]
