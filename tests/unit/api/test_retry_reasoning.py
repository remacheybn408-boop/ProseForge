"""retry/continue 复用消息落库的思考强度（V2-004 fix round 2）。

此前 retry 入队不带 reasoning_level，worker 端 ``payload.get("reasoning_level", "auto")``
静默回落 auto——用户选的 deep/max 在重试时丢失。现：显式指定优先；否则复用
``message.reasoning_snapshot`` 里落库的原级别；无快照才回落 auto。
"""

from __future__ import annotations

import types

import pytest

from proseforge.api.routes import conversations


class _FakeConversations:
    def __init__(self):
        self.statuses: list[tuple[str, str]] = []

    async def set_message_status(self, message_id, status):
        self.statuses.append((message_id, status))


class _FakeUow:
    def __init__(self):
        self.conversations = _FakeConversations()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        return None


class _FakeQueue:
    def __init__(self):
        self.enqueued: list[tuple[str, dict]] = []

    async def enqueue(self, task_name, payload):
        self.enqueued.append((task_name, payload))
        return "task-1"


def _request(queue: _FakeQueue):
    return types.SimpleNamespace(app=types.SimpleNamespace(state=types.SimpleNamespace(queue=queue)))


def _patch_dependencies(monkeypatch: pytest.MonkeyPatch, snapshot: dict | None) -> _FakeQueue:
    queue = _FakeQueue()
    message = types.SimpleNamespace(status="FAILED", reasoning_snapshot=snapshot)

    async def _owned_message(message_id, user, request):
        return message

    monkeypatch.setattr(conversations, "_owned_message", _owned_message)
    monkeypatch.setattr(conversations, "unit_of_work", lambda request: _FakeUow())
    return queue


@pytest.mark.asyncio
async def test_retry_reuses_the_messages_stored_reasoning_level(monkeypatch: pytest.MonkeyPatch):
    queue = _patch_dependencies(monkeypatch, {"level": "deep", "parameter": "reasoning_effort"})
    payload = conversations.MessageControlRequest(provider="anthropic", model="claude-sonnet")

    result = await conversations._requeue_message("m1", payload, _request(queue), types.SimpleNamespace(id="u1"), {"FAILED", "PARTIAL"})

    task_name, enqueued = queue.enqueued[0]
    assert task_name == "proseforge.chat.generate"
    assert enqueued["reasoning_level"] == "deep"  # 不再静默降级为 auto
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
async def test_retry_explicit_reasoning_level_wins_over_snapshot(monkeypatch: pytest.MonkeyPatch):
    queue = _patch_dependencies(monkeypatch, {"level": "deep"})
    payload = conversations.MessageControlRequest(provider="openai", model="gpt-4.1-mini", reasoning_level="fast")

    await conversations._requeue_message("m1", payload, _request(queue), types.SimpleNamespace(id="u1"), {"FAILED", "PARTIAL"})

    assert queue.enqueued[0][1]["reasoning_level"] == "fast"


@pytest.mark.asyncio
async def test_retry_without_snapshot_falls_back_to_auto(monkeypatch: pytest.MonkeyPatch):
    queue = _patch_dependencies(monkeypatch, None)
    payload = conversations.MessageControlRequest(provider="openai", model="gpt-4.1-mini")

    await conversations._requeue_message("m1", payload, _request(queue), types.SimpleNamespace(id="u1"), {"FAILED", "PARTIAL"})

    assert queue.enqueued[0][1]["reasoning_level"] == "auto"


@pytest.mark.asyncio
async def test_retry_reuses_level_from_unsupported_snapshot(monkeypatch: pytest.MonkeyPatch):
    # 原消息按不支持级别落库的快照也原样复用——重试复现原行为，不悄悄改级。
    queue = _patch_dependencies(monkeypatch, {"level": "max", "supported": False, "reason": "unsupported"})
    payload = conversations.MessageControlRequest(provider="local", model="writer")

    await conversations._requeue_message("m1", payload, _request(queue), types.SimpleNamespace(id="u1"), {"FAILED", "PARTIAL"})

    assert queue.enqueued[0][1]["reasoning_level"] == "max"
