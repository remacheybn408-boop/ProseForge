from __future__ import annotations
from proseforge.application.revision.approve_proposal import approve_proposal

class ApprovalState:
    def __init__(self): self.approved: dict[str, object] = {}
    def approve(self, proposal_id: str, proposal, current_content: str):
        if proposal_id in self.approved: return self.approved[proposal_id]
        result = approve_proposal(proposal, current_content); self.approved[proposal_id] = result; return result
