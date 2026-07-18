from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.application.conversations.edit_message import EditMessage
from proseforge.application.conversations.regenerate_reply import RegenerateReply
from proseforge.application.conversations.compare_branches import compare_messages
from proseforge.application.models.resolve_model import FALLBACK_CAPABILITIES
from proseforge.domain.model.capabilities import ModelCapabilities, ReasoningLevel, capabilities_from_model

router = APIRouter(prefix="/api/v2", tags=["conversation-branches"])


class V2MessageRequest(BaseModel):
    branch_id: str
    content: str = Field(min_length=1)
    client_request_id: str = Field(min_length=1, max_length=128)
    provider: str = "openai"
    model: str = "gpt-4.1-mini"
    reasoning_level: str = "auto"


def _reasoning_error(message: str, supported_levels: list[str]) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "code": "UNSUPPORTED_REASONING_LEVEL",
            "message": message,
            "retryable": False,
            "details": {"supported_levels": supported_levels},
        },
    )


def _validate_reasoning_level(level: str, capabilities: ModelCapabilities) -> None:
    try:
        selected = ReasoningLevel(level)
    except ValueError as exc:
        raise _reasoning_error(
            f"Unknown reasoning level {level!r}.",
            [item.value for item in ReasoningLevel],
        ) from exc
    if selected is not ReasoningLevel.AUTO and not capabilities.supports_reasoning:
        raise _reasoning_error(
            f"Model does not support reasoning level {selected.value!r}; use auto.",
            [ReasoningLevel.AUTO.value],
        )


class EditRequest(BaseModel):
    content: str = Field(min_length=1)


class RegenerateRequest(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4.1-mini"


@router.post("/conversations/{conversation_id}/messages")
async def append_message(conversation_id: str, payload: V2MessageRequest, request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> dict[str, str]:
    async with unit_of_work(request) as uow:
        if not await uow.conversations.branch_belongs_to_conversation(payload.branch_id, conversation_id, user.id):
            raise HTTPException(status_code=404, detail="conversation or branch not found")
        catalog = await uow.model_catalog.get(payload.provider, payload.model)
        capabilities = capabilities_from_model(catalog) if catalog is not None else FALLBACK_CAPABILITIES
        _validate_reasoning_level(payload.reasoning_level, capabilities)  # 入队前路由层校验
    from proseforge.application.conversations.send_message import SendMessage
    result = await SendMessage(lambda: unit_of_work(request), request.app.state.queue).execute(branch_id=payload.branch_id, content=payload.content, client_request_id=payload.client_request_id, user_id=user.id, provider=payload.provider, model=payload.model, reasoning_level=payload.reasoning_level)
    return {"user_message_id": result[0].id, "assistant_message_id": result[1].id, "task_id": result[2]}


@router.post("/conversations/{conversation_id}/messages/{message_id}/edit")
async def edit_message(conversation_id: str, message_id: str, payload: EditRequest, request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> dict[str, str]:
    try:
        result = await EditMessage(lambda: unit_of_work(request)).execute(conversation_id=conversation_id, message_id=message_id, content=payload.content, user_id=user.id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="message not found") from exc
    return {"branch_id": result.branch_id, "source_message_id": result.source_message_id, "replacement_message_id": result.replacement_message_id}


@router.post("/conversations/{conversation_id}/messages/{message_id}/regenerate")
async def regenerate_reply(conversation_id: str, message_id: str, payload: RegenerateRequest, request: Request, user: Annotated[AuthUser, Depends(current_user)]) -> dict[str, str]:
    async with unit_of_work(request) as uow:
        source = await uow.conversations.get_message(message_id)
        if source is None or not await uow.conversations.belongs_to_owner(conversation_id, user.id):
            raise HTTPException(status_code=404, detail="message not found")
        branch_id = source.branch_id
        # 候选与源消息共享 parent 边（用户消息）；无 parent 的历史消息退化为挂在自身。
        parent_message_id = source.parent_message_id or message_id
    result = await RegenerateReply(lambda: unit_of_work(request), request.app.state.queue).execute(branch_id=branch_id, parent_message_id=parent_message_id, user_id=user.id, provider=payload.provider, model=payload.model)
    return {"message_id": result[0].id, "task_id": result[1]}


@router.get("/conversations/{conversation_id}/branches")
async def list_branches(conversation_id: str, user: Annotated[AuthUser, Depends(current_user)], include_archived: bool = False, uow=Depends(unit_of_work)) -> list[dict[str, object]]:
    async with uow:
        return [branch.__dict__ for branch in await uow.conversations.list_branches(conversation_id, user.id, include_archived=include_archived)]


@router.get("/conversations/{conversation_id}/branches/{branch_id}/tree")
async def branch_tree(conversation_id: str, branch_id: str, user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work)) -> list[dict[str, object]]:
    async with uow:
        if not await uow.conversations.branch_belongs_to_conversation(branch_id, conversation_id, user.id):
            raise HTTPException(status_code=404, detail="branch not found")
        return [message.__dict__ for message in await uow.conversations.list_visible_messages(branch_id)]


@router.post("/conversations/{conversation_id}/branches/{branch_id}/archive")
async def archive_branch(conversation_id: str, branch_id: str, user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work)) -> dict[str, str]:
    async with uow:
        if not await uow.conversations.archive_branch(branch_id, conversation_id, user.id):
            raise HTTPException(status_code=404, detail="branch not found")
        await uow.commit()
    return {"id": branch_id, "status": "ARCHIVED"}


@router.get("/conversations/{conversation_id}/branches/compare")
async def compare_branches(conversation_id: str, left: str, right: str, user: Annotated[AuthUser, Depends(current_user)], uow=Depends(unit_of_work)) -> dict[str, object]:
    async with uow:
        if not await uow.conversations.branch_belongs_to_conversation(left, conversation_id, user.id) or not await uow.conversations.branch_belongs_to_conversation(right, conversation_id, user.id):
            raise HTTPException(status_code=404, detail="branch not found")
        return compare_messages(await uow.conversations.list_visible_messages(left), await uow.conversations.list_visible_messages(right))
