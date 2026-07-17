from proseforge.domain.revision.proposal import RevisionProposal


def reject_proposal(proposal: RevisionProposal) -> RevisionProposal:
    return RevisionProposal(proposal.base_version_id, proposal.before_hash, proposal.after_text, proposal.rationale, "REJECTED")
