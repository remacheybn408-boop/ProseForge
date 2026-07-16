from __future__ import annotations

from dataclasses import dataclass

from proseforge.domain.common.ids import new_id


@dataclass(frozen=True)
class Project:
    id: str
    owner_id: str
    slug: str
    title: str
    genre: str = ""
    style: str = ""
    language: str = "zh-CN"
    status: str = "ACTIVE"

    @classmethod
    def create(cls, *, owner_id: str, slug: str, title: str, genre: str = "", style: str = "") -> "Project":
        return cls(new_id(), owner_id, slug, title, genre, style)
