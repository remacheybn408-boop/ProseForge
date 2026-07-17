from __future__ import annotations
from proseforge.domain.agents.policy import authorize
from proseforge.application.revision.create_proposal import create_proposal

def create_chief_proposal(*, before: str, after: str, base_version_id: str, rationale: str):
    authorize("chief_editor", "create_revision")
    return create_proposal(base_version_id=base_version_id, before=before, after=after, rationale=rationale)
