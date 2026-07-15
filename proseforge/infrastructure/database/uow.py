from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from proseforge.infrastructure.database.repositories.chapter import SqlAlchemyChapterRepository
from proseforge.infrastructure.database.repositories.conversation import SqlAlchemyConversationRepository
from proseforge.infrastructure.database.repositories.project import SqlAlchemyProjectRepository
from proseforge.infrastructure.database.repositories.model_catalog import SqlAlchemyModelCatalogRepository
from proseforge.infrastructure.database.repositories.workflow import SqlAlchemyWorkflowRepository
from proseforge.infrastructure.database.repositories.attachment import SqlAlchemyAttachmentRepository
from proseforge.infrastructure.database.repositories.user import SqlAlchemyUserRepository


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        self.session: AsyncSession | None = None
        self._committed = False
        self.projects = None
        self.chapters = None
        self.conversations = None
        self.messages = None
        self.workflows = None
        self.attachments = None
        self.model_catalog = None
        self.users = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        self.session = self.session_factory()
        self._committed = False
        self.projects = SqlAlchemyProjectRepository(self.session)
        self.chapters = SqlAlchemyChapterRepository(self.session)
        self.conversations = SqlAlchemyConversationRepository(self.session)
        self.model_catalog = SqlAlchemyModelCatalogRepository(self.session)
        self.workflows = SqlAlchemyWorkflowRepository(self.session)
        self.attachments = SqlAlchemyAttachmentRepository(self.session)
        self.users = SqlAlchemyUserRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.session is None:
            return
        try:
            if exc_type is not None or not self._committed:
                await self.session.rollback()
        finally:
            await self.session.close()
            self.session = None

    async def commit(self) -> None:
        if self.session is None:
            raise RuntimeError("unit of work is not active")
        await self.session.commit()
        self._committed = True

    async def rollback(self) -> None:
        if self.session is not None:
            await self.session.rollback()
        self._committed = False
