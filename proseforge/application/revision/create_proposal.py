from proseforge.domain.revision.proposal import RevisionProposal, content_hash


def create_proposal(*, base_version_id: str, before: str, after: str, rationale: str) -> RevisionProposal:
    return RevisionProposal(base_version_id, content_hash(before), after, rationale)
