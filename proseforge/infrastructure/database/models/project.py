from __future__ import annotations

from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from proseforge.infrastructure.database.base import Base


class ProjectModel(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("owner_id", "slug"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    genre: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    style: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    language: Mapped[str] = mapped_column(String(32), default="zh-CN", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", nullable=False)
