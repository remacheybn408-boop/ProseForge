from __future__ import annotations

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


class ConversationCreateRequest(BaseModel):
    project_id: str
    title: str = "Untitled conversation"


class MessageRequest(BaseModel):
    branch_id: str
    content: str = Field(min_length=1)
    client_request_id: str = Field(min_length=1, max_length=128)


class BranchRequest(BaseModel):
    message_id: str
    name: str = Field(min_length=1, max_length=200)


@router.post("/conversations")
async def create_conversation(
    payload: ConversationCreateRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, str]:
    async with uow:
        # The project repository lookup is the ownership boundary.
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
    del conversation_id, user
    result = await SendMessage(
        lambda: unit_of_work(request), request.app.state.queue,
    ).execute(branch_id=payload.branch_id, content=payload.content, client_request_id=payload.client_request_id)
    return {"user_message_id": result[0].id, "assistant_message_id": result[1].id, "task_id": result[2]}


@router.get("/conversations/{conversation_id}/branches/{branch_id}/messages")
async def list_messages(
    conversation_id: str,
    branch_id: str,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> list[dict[str, object]]:
    del conversation_id, user
    async with uow:
        messages = await uow.conversations.list_visible_messages(branch_id)
        return [{"id": item.id, "role": item.role, "content": item.content, "status": item.status} for item in messages]


@router.post("/conversations/{conversation_id}/branches")
async def fork_branch(
    conversation_id: str,
    payload: BranchRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
) -> dict[str, str]:
    del user
    async with uow:
        branch = await uow.conversations.fork(conversation_id, payload.message_id, payload.name)
        await uow.commit()
        return {"id": branch.id, "name": branch.name}


@router.get("/conversations/{conversation_id}/events")
async def stream_events(conversation_id: str, request: Request, user: Annotated[AuthUser, Depends(current_user)]):
    del user
    last_id = request.headers.get("last-event-id")

    async def body():
        async for event in request.app.state.event_stream.subscribe(f"conversation:{conversation_id}", last_id):
            yield encode_sse(event_id=str(event["id"]), event=str(event.get("event", "message")), data=event)

    return StreamingResponse(body(), media_type="text/event-stream", headers={"cache-control": "no-cache", "x-accel-buffering": "no"})
