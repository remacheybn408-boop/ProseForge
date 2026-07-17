from __future__ import annotations
from proseforge.application.revision.approve_proposal import approve_proposal

class ApprovalState:
    def __init__(self): self.approved: set[str] = set()
    def approve(self, proposal_id: str, proposal, current_content: str):
        if proposal_id in self.approved: return proposal
        result = approve_proposal(proposal, current_content); self.approved.add(proposal_id); return result
