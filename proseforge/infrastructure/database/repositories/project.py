from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from proseforge.domain.project.entity import Project
from proseforge.infrastructure.database.models.project import ProjectModel


class SqlAlchemyProjectRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, project: Project) -> Project:
        self.session.add(ProjectModel(**project.__dict__))
        return project

    async def get_by_slug(self, owner_id: str, slug: str) -> Project | None:
        result = await self.session.execute(
            select(ProjectModel).where(ProjectModel.owner_id == owner_id, ProjectModel.slug == slug)
        )
        row = result.scalar_one_or_none()
        return None if row is None else Project(
            id=row.id,
            owner_id=row.owner_id,
            slug=row.slug,
            title=row.title,
            genre=row.genre,
            style=row.style,
            language=row.language,
            status=row.status,
        )

    async def get_by_id(self, owner_id: str, project_id: str) -> Project | None:
        row = await self.session.scalar(
            select(ProjectModel).where(ProjectModel.owner_id == owner_id, ProjectModel.id == project_id)
        )
        return None if row is None else self._entity(row)

    async def list_for_owner(self, owner_id: str) -> list[Project]:
        rows = await self.session.scalars(
            select(ProjectModel).where(ProjectModel.owner_id == owner_id).order_by(ProjectModel.title, ProjectModel.id)
        )
        return [self._entity(row) for row in rows]

    async def update(self, owner_id: str, project_id: str, *, title: str | None = None, genre: str | None = None, style: str | None = None) -> Project | None:
        row = await self.session.scalar(
            select(ProjectModel).where(ProjectModel.owner_id == owner_id, ProjectModel.id == project_id)
        )
        if row is None:
            return None
        for field, value in (("title", title), ("genre", genre), ("style", style)):
            if value is not None:
                setattr(row, field, value)
        await self.session.flush()
        return self._entity(row)

    async def delete(self, owner_id: str, project_id: str) -> bool:
        result = await self.session.execute(
            delete(ProjectModel).where(ProjectModel.owner_id == owner_id, ProjectModel.id == project_id)
        )
        return bool(result.rowcount)

    @staticmethod
    def _entity(row: ProjectModel) -> Project:
        return Project(
            id=row.id,
            owner_id=row.owner_id,
            slug=row.slug,
            title=row.title,
            genre=row.genre,
            style=row.style,
            language=row.language,
            status=row.status,
        )
