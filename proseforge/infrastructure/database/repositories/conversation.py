from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.common.ids import new_id
from proseforge.domain.conversation.entity import Conversation, ConversationBranch, Message, MessageChunk
from proseforge.infrastructure.database.models.conversation import ConversationBranchModel, ConversationModel, MessageChunkModel, MessageModel


class SqlAlchemyConversationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, conversation: Conversation) -> ConversationBranch:
        self.session.add(ConversationModel(id=conversation.id, project_id=conversation.project_id, title=conversation.title))
        branch = ConversationBranch(id=new_id(), conversation_id=conversation.id, name="Main")
        self.session.add(ConversationBranchModel(**branch.__dict__))
        await self.session.flush()
        return branch

    async def append_message(self, branch_id: str, role: str, content: str, client_request_id: str | None = None, status: str = "COMPLETED") -> Message:
        if client_request_id:
            existing = await self.session.scalar(select(MessageModel).where(MessageModel.client_request_id == client_request_id))
            if existing:
                return self._message(existing)
        next_sequence = (await self.session.scalar(select(func.coalesce(func.max(MessageModel.sequence_no), 0)).where(MessageModel.branch_id == branch_id))) + 1
        message = Message(id=new_id(), branch_id=branch_id, role=role, content=content, client_request_id=client_request_id, status=status)
        self.session.add(MessageModel(**message.__dict__, sequence_no=next_sequence))
        await self.session.flush()
        return message

    async def fork(self, conversation_id: str, forked_from_message_id: str, name: str) -> ConversationBranch:
        source = await self.session.scalar(select(MessageModel).where(MessageModel.id == forked_from_message_id))
        if source is None:
            raise ValueError("fork point message does not exist")
        branch = ConversationBranch(id=new_id(), conversation_id=conversation_id, name=name, parent_branch_id=source.branch_id, forked_from_message_id=forked_from_message_id)
        self.session.add(ConversationBranchModel(**branch.__dict__))
        await self.session.flush()
        return branch

    async def list_visible_messages(self, branch_id: str) -> list[Message]:
        branch = await self.session.get(ConversationBranchModel, branch_id)
        if branch is None:
            return []
        own_rows = list((await self.session.scalars(select(MessageModel).where(MessageModel.branch_id == branch_id).order_by(MessageModel.sequence_no, MessageModel.id))).all())
        own = [self._message(item) for item in own_rows]
        if branch.parent_branch_id is None:
            return own
        ancestors = await self.list_visible_messages(branch.parent_branch_id)
        if branch.forked_from_message_id:
            ids = [item.id for item in ancestors]
            if branch.forked_from_message_id not in ids:
                raise ValueError("fork point is not visible from parent branch")
            ancestors = ancestors[: ids.index(branch.forked_from_message_id) + 1]
        return ancestors + own

    async def append_chunk(self, message_id: str, chunk_index: int, event_type: str, content: str) -> MessageChunk:
        existing = await self.session.scalar(select(MessageChunkModel).where(MessageChunkModel.message_id == message_id, MessageChunkModel.chunk_index == chunk_index))
        if existing:
            return self._chunk(existing)
        chunk = MessageChunk(id=new_id(), message_id=message_id, chunk_index=chunk_index, event_type=event_type, content=content)
        self.session.add(MessageChunkModel(**chunk.__dict__))
        await self.session.flush()
        return chunk

    async def get_message(self, message_id: str) -> Message | None:
        row = await self.session.get(MessageModel, message_id)
        return self._message(row) if row else None

    async def conversation_id_for_message(self, message_id: str) -> str | None:
        return await self.session.scalar(
            select(ConversationModel.id)
            .join(ConversationBranchModel, ConversationBranchModel.conversation_id == ConversationModel.id)
            .join(MessageModel, MessageModel.branch_id == ConversationBranchModel.id)
            .where(MessageModel.id == message_id)
        )

    async def belongs_to_owner(self, conversation_id: str, owner_id: str) -> bool:
        from proseforge.infrastructure.database.models.project import ProjectModel
        row = await self.session.scalar(
            select(ConversationModel.id)
            .join(ProjectModel, ProjectModel.id == ConversationModel.project_id)
            .where(ConversationModel.id == conversation_id, ProjectModel.owner_id == owner_id)
        )
        return row is not None

    async def branch_belongs_to_conversation(self, branch_id: str, conversation_id: str, owner_id: str) -> bool:
        from proseforge.infrastructure.database.models.project import ProjectModel
        row = await self.session.scalar(
            select(ConversationBranchModel.id)
            .join(ConversationModel, ConversationModel.id == ConversationBranchModel.conversation_id)
            .join(ProjectModel, ProjectModel.id == ConversationModel.project_id)
            .where(
                ConversationBranchModel.id == branch_id,
                ConversationBranchModel.conversation_id == conversation_id,
                ProjectModel.owner_id == owner_id,
            )
        )
        return row is not None

    async def set_message_status(self, message_id: str, status: str) -> None:
        row = await self.session.get(MessageModel, message_id)
        if row is None:
            raise ValueError("message does not exist")
        row.status = status
        await self.session.flush()

    @staticmethod
    def _message(item: MessageModel) -> Message:
        return Message(id=item.id, branch_id=item.branch_id, role=item.role, content=item.content, client_request_id=item.client_request_id, status=item.status)

    @staticmethod
    def _chunk(item: MessageChunkModel) -> MessageChunk:
        return MessageChunk(id=item.id, message_id=item.message_id, chunk_index=item.chunk_index, event_type=item.event_type, content=item.content)
