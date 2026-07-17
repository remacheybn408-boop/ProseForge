from proseforge.domain.revision.proposal import RevisionProposal


def approve_proposal(proposal: RevisionProposal, current_content: str) -> RevisionProposal:
    return proposal.approve(__import__("hashlib").sha256(current_content.encode()).hexdigest())
