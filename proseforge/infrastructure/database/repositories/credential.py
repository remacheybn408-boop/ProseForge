from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.remaining import ProviderCredentialModel


class SqlAlchemyCredentialRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: str, provider: str, encrypted_payload: str, record_id: str | None = None) -> ProviderCredentialModel:
        record = ProviderCredentialModel(id=record_id or new_id(), user_id=user_id, provider=provider, encrypted_payload=encrypted_payload)
        self.session.add(record)
        await self.session.flush()
        return record

    async def list_for_user(self, user_id: str) -> list[ProviderCredentialModel]:
        rows = await self.session.scalars(
            select(ProviderCredentialModel).where(ProviderCredentialModel.user_id == user_id).order_by(ProviderCredentialModel.provider)
        )
        return list(rows)
