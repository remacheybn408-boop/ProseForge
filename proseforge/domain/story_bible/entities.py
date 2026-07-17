from __future__ import annotations

from dataclasses import dataclass

from proseforge.domain.common.ids import new_id


VALID_KINDS = {"character", "relationship", "location", "timeline_event", "world_rule", "plot_thread", "style_rule", "promise"}


@dataclass(frozen=True)
class StoryFact:
    project_id: str
    kind: str
    key: str
    value: dict[str, object]
    pinned: bool = False
    status: str = "active"
    id: str = ""

    @classmethod
    def create(cls, project_id: str, kind: str, key: str, value: dict[str, object]) -> "StoryFact":
        if kind not in VALID_KINDS:
            raise ValueError("unsupported story bible kind")
        return cls(project_id, kind, key, value, id=new_id())
