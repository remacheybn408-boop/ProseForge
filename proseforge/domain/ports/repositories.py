from __future__ import annotations

from typing import Protocol


class ProjectRepository(Protocol):
    async def add(self, project: object) -> object: ...

    async def get_by_slug(self, owner_id: str, slug: str) -> object | None: ...


class ConversationRepository(Protocol):
    async def get(self, conversation_id: str) -> object | None: ...


class MessageRepository(Protocol):
    async def get(self, message_id: str) -> object | None: ...


class WorkflowRepository(Protocol):
    async def get(self, workflow_id: str) -> object | None: ...


class UnitOfWork(Protocol):
    projects: ProjectRepository
    conversations: ConversationRepository
    messages: MessageRepository
    workflows: WorkflowRepository

    async def __aenter__(self) -> "UnitOfWork": ...

    async def __aexit__(self, exc_type, exc, tb) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...
