from __future__ import annotations
from datetime import datetime
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from proseforge.infrastructure.database.base import Base


class RevisionProposalModel(Base):
    __tablename__ = "revision_proposals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    chapter_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    base_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    before_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    after_text: Mapped[str] = mapped_column(Text, nullable=False)
    after_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="PROPOSED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
