from sqlalchemy import select
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
