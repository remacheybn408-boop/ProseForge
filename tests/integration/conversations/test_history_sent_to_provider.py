from __future__ import annotations

import base64
import hashlib
import json
import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from proseforge.domain.common.ids import new_id
from proseforge.domain.conversation.entity import Conversation
from proseforge.domain.project.entity import Project
from proseforge.domain.ports.model_provider import GenerationEvent, ProviderModel
from proseforge.infrastructure.database.base import Base
from proseforge.infrastructure.database.models.conversation import ConversationEventModel, MessageModel
from proseforge.infrastructure.database.models.remaining import ContextSnapshotModel
from proseforge.infrastructure.database.models.story_bible import StoryBibleEntryModel
from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork
from proseforge.infrastructure.security.credential_cipher import CredentialCipher
from proseforge.settings import Settings, get_settings
from proseforge.workflows.tasks import generate_chat

MASTER_KEY = base64.b64encode(b"k" * 32).decode()


class SpyProvider:
    provider_id = "openai"

    def __init__(self):
        self.requests = []

    async def stream(self, request):
        self.requests.append(request)
        yield GenerationEvent("content.delta", "暗")
        yield GenerationEvent("content.delta", "涌")


@pytest.fixture()
def chat_settings(tmp_path, monkeypatch):
    database_url = os.environ.get("PROSEFORGE_TEST_DATABASE_URL")
    profile = "test" if database_url else "native"
    if not database_url:
        database_url = f"sqlite+aiosqlite:///{(tmp_path / 'chat.db').as_posix()}"
    monkeypatch.setenv("PROSEFORGE_DATABASE_URL", database_url)
    monkeypatch.setenv("PROSEFORGE_RUNTIME_PROFILE", profile)
    monkeypatch.setenv("PROSEFORGE_MASTER_KEY", MASTER_KEY)
    get_settings.cache_clear()
    yield Settings(
        database_url=database_url,
        runtime_profile=profile,
        master_key=MASTER_KEY,
        blob_root=str(tmp_path / "blobs"),
        backup_root=str(tmp_path / "backups"),
    )
    get_settings.cache_clear()


async def _seed(settings: Settings, *, with_catalog: bool = True) -> dict[str, str]:
    engine, factory = create_engine_and_sessionmaker(settings)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with SqlAlchemyUnitOfWork(factory) as uow:
            user = await uow.users.create("writer@example.local", "hash-not-used", "ADMIN")
            project = Project.create(owner_id=user.id, slug="novel", title="Novel")
            await uow.projects.add(project)
            credential_id = "cred-test"
            associated = f"{user.id}:openai:{credential_id}".encode()
            encrypted = CredentialCipher(base64.b64decode(MASTER_KEY)).encrypt(
                json.dumps({"api_key": "sk-test"}).encode(), associated_data=associated
            )
            await uow.credentials.create(user.id, "openai", base64.b64encode(encrypted).decode(), record_id=credential_id)
            if with_catalog:
                await uow.model_catalog.upsert([
                    ProviderModel("openai", "gpt-test", "GPT Test", {"reasoning": True, "reasoning_parameter": "effort"}, context_window=2048, max_output_tokens=333)
                ])
            conversation = Conversation.create(project.id, "Chat")
            main = await uow.conversations.create(conversation)
            await uow.conversations.append_message(main.id, "user", "第一章写得再暗一点")
            second = await uow.conversations.append_message(main.id, "assistant", "好的，基调压暗")
            await uow.conversations.append_message(main.id, "user", "主线分支的第三条")
            fork = await uow.conversations.fork(conversation.id, second.id, "alternative")
            await uow.conversations.append_message(fork.id, "user", "分叉后的新问题")
            target = await uow.conversations.append_message(fork.id, "assistant", "", None, "PENDING")
            fact_id = new_id()
            now = datetime.now(UTC)
            uow.session.add(StoryBibleEntryModel(
                id=fact_id, project_id=project.id, kind="character", key="烛龙",
                value_json=json.dumps({"note": "睁眼为昼"}, ensure_ascii=False),
                status="active", confidence=1.0, source="user", pinned=True, version=1, created_at=now, updated_at=now,
            ))
            await uow.commit()
            return {"user_id": user.id, "project_id": project.id, "message_id": target.id, "fact_id": fact_id}
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_full_branch_history_is_sent_to_provider(chat_settings, monkeypatch):
    seeded = await _seed(chat_settings)
    spy = SpyProvider()
    monkeypatch.setattr("proseforge.providers.factory.build_provider", lambda *args, **kwargs: spy)

    result = await generate_chat({
        "message_id": seeded["message_id"],
        "user_id": seeded["user_id"],
        "provider": "openai",
        "model": "gpt-test",
        "reasoning_level": "deep",
    })

    assert result == "completed"
    assert len(spy.requests) == 1
    request = spy.requests[0]
    texts = [block["text"] for block in request.input_blocks]
    assert texts == ["第一章写得再暗一点", "好的，基调压暗", "分叉后的新问题"]  # 全分支历史，含 fork 前祖先
    assert "主线分支的第三条" not in texts  # fork 点之后的主分支消息不可见
    assert request.system_blocks, "system blocks must not be empty"
    assert any("烛龙" in str(block.get("text", "")) for block in request.system_blocks)  # pinned story fact 注入
    assert request.max_output_tokens == 333  # catalog 值
    assert request.reasoning is not None and "effort" in str(request.reasoning)

    engine, factory = create_engine_and_sessionmaker(chat_settings)
    try:
        async with factory() as session:
            snapshots = list((await session.scalars(select(ContextSnapshotModel))).all())
            assert len(snapshots) == 1
            snapshot_payload = json.loads(snapshots[0].payload)
            assert seeded["fact_id"] in snapshot_payload["injected_fact_ids"]
            assert "omitted" in snapshot_payload
            assert snapshot_payload["message_ids"], "snapshot must record the sent history"

            row = await session.get(MessageModel, seeded["message_id"])
            model_snapshot = json.loads(row.model_snapshot_json)
            assert model_snapshot["model"] == "gpt-test"
            assert model_snapshot["source"] == "catalog"
            assert model_snapshot["context_snapshot_id"] == snapshots[0].id
            reasoning_snapshot = json.loads(row.reasoning_snapshot_json)
            assert reasoning_snapshot["level"] == "deep"
            assert row.content_hash == hashlib.sha256("暗涌".encode()).hexdigest()

            events = list((await session.scalars(select(ConversationEventModel).order_by(ConversationEventModel.event_sequence))).all())
            event_types = [event.event_type for event in events]
            assert "message.started" in event_types
            assert "message.completed" in event_types
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unknown_model_uses_conservative_fallback(chat_settings, monkeypatch):
    seeded = await _seed(chat_settings, with_catalog=False)
    spy = SpyProvider()
    monkeypatch.setattr("proseforge.providers.factory.build_provider", lambda *args, **kwargs: spy)

    result = await generate_chat({
        "message_id": seeded["message_id"],
        "user_id": seeded["user_id"],
        "provider": "openai",
        "model": "gpt-unknown",
        "reasoning_level": "deep",
    })

    assert result == "completed"  # 未知模型不得让生成崩溃
    request = spy.requests[0]
    assert request.max_output_tokens == 1024  # fallback 上限

    engine, factory = create_engine_and_sessionmaker(chat_settings)
    try:
        async with factory() as session:
            row = await session.get(MessageModel, seeded["message_id"])
            model_snapshot = json.loads(row.model_snapshot_json)
            assert model_snapshot["source"] == "fallback"
            assert model_snapshot["context_window"] == 8192
            reasoning_snapshot = json.loads(row.reasoning_snapshot_json)
            assert reasoning_snapshot["level"] == "deep"
            assert reasoning_snapshot["supported"] is False
    finally:
        await engine.dispose()
