from __future__ import annotations

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.api.sse.encoder import encode_sse
from proseforge.application.auth.service import AuthUser
from proseforge.application.conversations.send_message import SendMessage
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1", tags=["conversations"])

SSE_HEARTBEAT_SECONDS = 15.0


class ConversationCreateRequest(BaseModel):
    project_id: str
    title: str = "Untitled conversation"


class MessageRequest(BaseModel):
    branch_id: str
    content: str = Field(min_length=1)
    client_request_id: str = Field(min_length=1, max_length=128)
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    reasoning_level: str = "auto"  # v1 容忍透传，不在此校验


class BranchRequest(BaseModel):
    message_id: str
    name: str = Field(min_length=1, max_length=200)


class MessageControlRequest(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4.1-mini"


@router.post("/conversations")
async def create_conversation(
    payload: ConversationCreateRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, str]:
    async with uow:
        # The project repository lookup is the ownership boundary.
        project = await uow.projects.get_by_id(user.id, payload.project_id)
        if project is None:
            project = await uow.projects.get_by_slug(user.id, payload.project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="project not found")
        from proseforge.domain.conversation.entity import Conversation
        conversation = Conversation.create(project.id, payload.title)
        branch = await uow.conversations.create(conversation)
        await uow.commit()
        return {"id": conversation.id, "branch_id": branch.id, "title": conversation.title}


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: str,
    payload: MessageRequest,
    request: Request,
    user: Annotated[AuthUser, Depends(current_user)],
) -> dict[str, str]:
    async with unit_of_work(request) as uow:
        if not await uow.conversations.branch_belongs_to_conversation(payload.branch_id, conversation_id, user.id):
            raise HTTPException(status_code=404, detail="conversation or branch not found")
    result = await SendMessage(
        lambda: unit_of_work(request), request.app.state.queue,
    ).execute(branch_id=payload.branch_id, content=payload.content, client_request_id=payload.client_request_id, user_id=user.id, provider=payload.provider, model=payload.model, reasoning_level=payload.reasoning_level)
    return {"user_message_id": result[0].id, "assistant_message_id": result[1].id, "task_id": result[2]}


@router.get("/conversations/{conversation_id}/branches/{branch_id}/messages")
async def list_messages(
    conversation_id: str,
    branch_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> list[dict[str, object]]:
    async with uow:
        if not await uow.conversations.branch_belongs_to_conversation(branch_id, conversation_id, user.id):
            raise HTTPException(status_code=404, detail="conversation or branch not found")
        messages = await uow.conversations.list_visible_messages(branch_id)
        return [{"id": item.id, "role": item.role, "content": item.content, "status": item.status} for item in messages]


@router.post("/conversations/{conversation_id}/branches")
async def fork_branch(
    conversation_id: str,
    payload: BranchRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, str]:
    async with uow:
        branch = await uow.conversations.fork_owned(conversation_id, payload.message_id, payload.name, user.id)
        if branch is None:
            raise HTTPException(status_code=404, detail="conversation or fork point not found")
        await uow.commit()
        return {"id": branch.id, "name": branch.name}


async def _owned_message(message_id: str, user: AuthUser, request: Request):
    async with unit_of_work(request) as uow:
        conversation_id = await uow.conversations.conversation_id_for_message(message_id)
        if conversation_id is None or not await uow.conversations.belongs_to_owner(conversation_id, user.id):
            raise HTTPException(status_code=404, detail="message not found")
        message = await uow.conversations.get_message(message_id)
        if message is None:
            raise HTTPException(status_code=404, detail="message not found")
        return message


@router.post("/messages/{message_id}/stop")
async def stop_message(message_id: str, request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> dict[str, str]:
    message = await _owned_message(message_id, user, request)
    if message.status not in {"PENDING", "STREAMING", "PARTIAL"}:
        raise HTTPException(status_code=409, detail="message cannot be stopped in its current state")
    async with unit_of_work(request) as uow:
        await uow.conversations.set_message_status(message_id, "CANCELLED")
        await uow.commit()
    return {"id": message_id, "status": "CANCELLED"}


async def _requeue_message(message_id: str, payload: MessageControlRequest, request: Request, user: AuthUser, allowed: set[str]) -> dict[str, str]:
    message = await _owned_message(message_id, user, request)
    if message.status not in allowed:
        raise HTTPException(status_code=409, detail="message is not recoverable in its current state")
    async with unit_of_work(request) as uow:
        await uow.conversations.set_message_status(message_id, "PENDING")
        await uow.commit()
    task_id = await request.app.state.queue.enqueue("proseforge.chat.generate", {"message_id": message_id, "user_id": user.id, "provider": payload.provider, "model": payload.model})
    return {"id": message_id, "status": "PENDING", "task_id": task_id}


@router.post("/messages/{message_id}/retry")
async def retry_message(message_id: str, payload: MessageControlRequest, request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> dict[str, str]:
    return await _requeue_message(message_id, payload, request, user, {"FAILED", "PARTIAL"})


@router.post("/messages/{message_id}/continue")
async def continue_message(message_id: str, payload: MessageControlRequest, request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> dict[str, str]:
    return await _requeue_message(message_id, payload, request, user, {"PARTIAL"})


@router.get("/conversations/{conversation_id}/events")
async def stream_events(conversation_id: str, request: Request, user: Annotated[AuthUser, Depends(current_user)]):
    async with unit_of_work(request) as uow:
        if not await uow.conversations.belongs_to_owner(conversation_id, user.id):
            raise HTTPException(status_code=404, detail="conversation not found")
    last_id = request.headers.get("last-event-id")

    async def body():
        subscription = request.app.state.event_stream.subscribe(f"conversation:{conversation_id}", last_id)
        iterator = subscription.__aiter__()
        pending: asyncio.Task | None = None
        try:
            while True:
                if pending is None:
                    pending = asyncio.ensure_future(iterator.__anext__())
                done, _ = await asyncio.wait({pending}, timeout=SSE_HEARTBEAT_SECONDS)
                if not done:
                    yield b": heartbeat\n\n"
                    continue
                pending = None
                try:
                    event = done.pop().result()
                except StopAsyncIteration:
                    return
                yield encode_sse(event_id=str(event["id"]), event=str(event.get("event", "message")), data=event)
        finally:
            # 客户端断连时 StreamingResponse 取消本生成器；清理待取的轮询任务。
            if pending is not None:
                pending.cancel()
            await subscription.aclose()

    return StreamingResponse(body(), media_type="text/event-stream", headers={"cache-control": "no-cache", "x-accel-buffering": "no"})
