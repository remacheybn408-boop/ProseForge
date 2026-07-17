from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.common.ids import new_id
from proseforge.infrastructure.database.models.project import ProjectModel
from proseforge.infrastructure.database.models.remaining import ContextItemModel, ContextSnapshotModel


class SqlAlchemyContextRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_owned(self, project_id: str, owner_id: str) -> list[ContextItemModel]:
        rows = await self.session.scalars(
            select(ContextItemModel).join(ProjectModel, ProjectModel.id == ContextItemModel.project_id).where(
                ContextItemModel.project_id == project_id, ProjectModel.owner_id == owner_id
            ).order_by(ContextItemModel.priority.desc(), ContextItemModel.id)
        )
        return list(rows)

    async def get_owned(self, item_id: str, owner_id: str) -> ContextItemModel | None:
        return await self.session.scalar(
            select(ContextItemModel).join(ProjectModel, ProjectModel.id == ContextItemModel.project_id).where(
                ContextItemModel.id == item_id, ProjectModel.owner_id == owner_id
            )
        )

    async def add(self, project_id: str, source_type: str, content: str, source_id: str = "manual") -> ContextItemModel:
        item = ContextItemModel(id=new_id(), project_id=project_id, source_type=source_type, source_id=source_id, content=content, provenance=json.dumps({"source": source_type}))
        self.session.add(item)
        await self.session.flush()
        return item

    async def snapshot(self, project_id: str, items: list[ContextItemModel]) -> ContextSnapshotModel:
        payload = {
            "items": [
                {
                    "id": item.id,
                    "source_type": item.source_type,
                    "source_id": item.source_id,
                    "content": item.content,
                    "pinned": item.pinned,
                    "priority": item.priority,
                    "excluded": item.excluded,
                    "provenance": json.loads(item.provenance or "{}"),
                }
                for item in items
            ]
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        snapshot = ContextSnapshotModel(id=new_id(), project_id=project_id, snapshot_hash=hashlib.sha256(encoded.encode()).hexdigest(), payload=encoded)
        self.session.add(snapshot)
        await self.session.flush()
        return snapshot

    async def restore_snapshot(self, project_id: str, snapshot: ContextSnapshotModel) -> list[ContextItemModel]:
        if snapshot.project_id != project_id:
            raise ValueError("context snapshot belongs to another project")
        rows = list(await self.session.scalars(select(ContextItemModel).where(ContextItemModel.project_id == project_id)))
        by_id = {item.id: item for item in rows}
        payload = json.loads(snapshot.payload or "{}")
        for source in payload.get("items", []):
            if not isinstance(source, dict):
                continue
            item_id = str(source.get("id", ""))
            item = by_id.get(item_id)
            if item is None:
                item = ContextItemModel(
                    id=new_id(),
                    project_id=project_id,
                    source_type=str(source.get("source_type", "manual")),
                    source_id=str(source.get("source_id", "manual")),
                    content=str(source.get("content", "")),
                    pinned=bool(source.get("pinned", False)),
                    priority=int(source.get("priority", 0) or 0),
                    excluded=bool(source.get("excluded", False)),
                    provenance=json.dumps(source.get("provenance", {}), ensure_ascii=False),
                )
                self.session.add(item)
                rows.append(item)
                continue
            item.source_type = str(source.get("source_type", item.source_type))
            item.source_id = str(source.get("source_id", item.source_id))
            item.content = str(source.get("content", item.content))
            item.pinned = bool(source.get("pinned", item.pinned))
            item.priority = int(source.get("priority", item.priority) or 0)
            item.excluded = bool(source.get("excluded", item.excluded))
            item.provenance = json.dumps(source.get("provenance", json.loads(item.provenance or "{}")), ensure_ascii=False)
        await self.session.flush()
        return sorted(rows, key=lambda item: (-int(item.priority or 0), item.id))

    async def get_snapshot_owned(self, snapshot_id: str, owner_id: str) -> ContextSnapshotModel | None:
        return await self.session.scalar(
            select(ContextSnapshotModel)
            .join(ProjectModel, ProjectModel.id == ContextSnapshotModel.project_id)
            .where(ContextSnapshotModel.id == snapshot_id, ProjectModel.owner_id == owner_id)
        )
