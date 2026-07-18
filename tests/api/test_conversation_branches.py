from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient

from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork


def _crid() -> str:
    return uuid.uuid4().hex


def _create_project(auth_client) -> str:
    response = auth_client.post_json("/api/v1/projects", {"slug": f"proj-{uuid.uuid4().hex[:12]}", "title": "Branch Novel"})
    assert response.status_code == 201
    return response.json()["id"]


def _create_conversation(auth_client, project_id: str) -> dict:
    response = auth_client.post_json("/api/v1/conversations", {"project_id": project_id, "title": "chat"})
    assert response.status_code == 200
    return response.json()


def _send(auth_client, conversation: dict, content: str, client_request_id: str | None = None, **extra):
    payload = {"branch_id": conversation["branch_id"], "content": content, "client_request_id": client_request_id or _crid(), **extra}
    response = auth_client.post_json(f"/api/v2/conversations/{conversation['id']}/messages", payload)
    assert response.status_code == 200
    return response.json()


def test_edit_keeps_original_message_content(auth_client):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    sent = _send(auth_client, conversation, "original question")

    edited = auth_client.post_json(
        f"/api/v2/conversations/{conversation['id']}/messages/{sent['user_message_id']}/edit",
        {"content": "edited question"},
    )
    assert edited.status_code == 200

    main_messages = auth_client.get(f"/api/v1/conversations/{conversation['id']}/branches/{conversation['branch_id']}/messages").json()
    original = next(message for message in main_messages if message["id"] == sent["user_message_id"])
    assert original["content"] == "original question"  # 原文不可变

    tree = auth_client.get(f"/api/v2/conversations/{conversation['id']}/branches/{edited.json()['branch_id']}/tree").json()
    assert tree[-1]["content"] == "edited question"
    assert tree[-1]["id"] == edited.json()["replacement_message_id"]


def test_edit_creates_branch_with_single_parent_edge(auth_client):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    sent = _send(auth_client, conversation, "fork me")

    edited = auth_client.post_json(
        f"/api/v2/conversations/{conversation['id']}/messages/{sent['user_message_id']}/edit",
        {"content": "forked"},
    )
    assert edited.status_code == 200

    branches = auth_client.get(f"/api/v2/conversations/{conversation['id']}/branches").json()
    children = [branch for branch in branches if branch["parent_branch_id"] == conversation["branch_id"]]
    assert len(children) == 1  # 新分支恰一条 parent 边
    assert children[0]["id"] == edited.json()["branch_id"]
    assert children[0]["forked_from_message_id"] == sent["user_message_id"]


def test_cross_user_access_returns_404(auth_client, client, api_settings):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    sent = _send(auth_client, conversation, "private")

    app = client.app
    other_email = f"other-{uuid.uuid4().hex[:8]}@example.local"

    async def create_other_user():
        # 独立引擎：避免在测试线程的事件循环里复用 app loop 的连接池。
        from proseforge.infrastructure.database.session import create_engine_and_sessionmaker

        engine, factory = create_engine_and_sessionmaker(api_settings)
        try:
            async with SqlAlchemyUnitOfWork(factory) as uow:
                await uow.users.create(other_email, app.state.auth.hash_password("twelve-char-pw"), "USER")
                await uow.commit()
        finally:
            await engine.dispose()

    asyncio.run(create_other_user())
    other = TestClient(app)
    login = other.post("/api/v1/auth/login", json={"email": other_email, "password": "twelve-char-pw"}, headers={"Origin": "http://testserver"})
    assert login.status_code == 200

    assert other.get(f"/api/v1/conversations/{conversation['id']}/branches/{conversation['branch_id']}/messages").status_code == 404
    edit = other.post(
        f"/api/v2/conversations/{conversation['id']}/messages/{sent['user_message_id']}/edit",
        json={"content": "hijack"},
        headers={"Origin": "http://testserver"},
    )
    assert edit.status_code == 404


def test_duplicate_client_request_id_is_idempotent(auth_client):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    crid = _crid()

    first = _send(auth_client, conversation, "same request", crid)
    second = _send(auth_client, conversation, "same request", crid)

    assert second["user_message_id"] == first["user_message_id"]
    assert second["assistant_message_id"] == first["assistant_message_id"]
    assert second["task_id"] == "deduplicated"
    messages = auth_client.get(f"/api/v1/conversations/{conversation['id']}/branches/{conversation['branch_id']}/messages").json()
    assert len([message for message in messages if message["role"] == "user"]) == 1


def test_reconnect_with_last_event_id_does_not_duplicate_deltas(auth_client, api_settings):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)

    async def publish_events():
        # 独立引擎：避免在测试线程的事件循环里复用 app loop 的连接池。
        from proseforge.infrastructure.database.session import create_engine_and_sessionmaker
        from proseforge.infrastructure.events.database import DatabaseEventStream

        engine, factory = create_engine_and_sessionmaker(api_settings)
        try:
            stream = DatabaseEventStream(factory)
            await stream.publish(f"conversation:{conversation['id']}", {"event": "content.delta", "message_id": "m", "text": "one"})
            await stream.publish(f"conversation:{conversation['id']}", {"event": "content.delta", "message_id": "m", "text": "two"})
            await stream.publish(f"conversation:{conversation['id']}", {"event": "message.completed", "message_id": "m", "status": "COMPLETED"})
        finally:
            await engine.dispose()

    asyncio.run(publish_events())

    with auth_client.stream("GET", f"/api/v1/conversations/{conversation['id']}/events", headers={"Last-Event-ID": "1"}) as response:
        assert response.status_code == 200
        body = b"".join(response.iter_bytes()).decode()

    assert '"text": "one"' not in body and "one" not in body  # 重放起点之后，不重复 delta
    assert body.count("content.delta") == 1
    assert "two" in body
    assert "message.completed" in body  # live tail 在 terminal 事件后结束


def test_sse_stream_emits_heartbeat_comments(auth_client, monkeypatch):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    monkeypatch.setattr("proseforge.api.routes.conversations.SSE_HEARTBEAT_SECONDS", 0.2)

    with auth_client.stream("GET", f"/api/v1/conversations/{conversation['id']}/events") as response:
        assert response.status_code == 200
        first_chunk = next(response.iter_bytes())

    assert b": heartbeat" in first_chunk


def test_regenerate_keeps_both_candidates(auth_client):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    sent = _send(auth_client, conversation, "give me two takes")

    regenerated = auth_client.post_json(
        f"/api/v2/conversations/{conversation['id']}/messages/{sent['assistant_message_id']}/regenerate",
        {"provider": "openai", "model": "gpt-4.1-mini"},
    )
    assert regenerated.status_code == 200
    candidate = regenerated.json()["message_id"]
    assert candidate != sent["assistant_message_id"]

    tree = auth_client.get(f"/api/v2/conversations/{conversation['id']}/branches/{conversation['branch_id']}/tree").json()
    assistants = [message for message in tree if message["role"] == "assistant"]
    assert len(assistants) == 2  # 两候选都在
    assert {message["id"] for message in assistants} == {sent["assistant_message_id"], candidate}


def test_v2_send_rejects_unsupported_reasoning_level(auth_client):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    payload = {
        "branch_id": conversation["branch_id"],
        "content": "think hard",
        "client_request_id": _crid(),
        "provider": "openai",
        "model": "gpt-4.1-mini",
        "reasoning_level": "deep",
    }
    response = auth_client.post_json(f"/api/v2/conversations/{conversation['id']}/messages", payload)
    assert response.status_code == 422
    body = response.json()
    assert "auto" in str(body)  # 响应必须列出支持级别
    assert "deep" not in str(body.get("detail", {}).get("details", {}).get("supported_levels", []))


def test_v2_send_rejects_unknown_reasoning_level(auth_client):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    payload = {
        "branch_id": conversation["branch_id"],
        "content": "think weird",
        "client_request_id": _crid(),
        "reasoning_level": "ludicrous",
    }
    response = auth_client.post_json(f"/api/v2/conversations/{conversation['id']}/messages", payload)
    assert response.status_code == 422
    assert "supported_levels" in str(response.json())


def test_v1_send_tolerates_reasoning_level(auth_client):
    project_id = _create_project(auth_client)
    conversation = _create_conversation(auth_client, project_id)
    payload = {
        "branch_id": conversation["branch_id"],
        "content": "v1 stays tolerant",
        "client_request_id": _crid(),
        "reasoning_level": "deep",
    }
    response = auth_client.post_json(f"/api/v1/conversations/{conversation['id']}/messages", payload)
    assert response.status_code == 200
