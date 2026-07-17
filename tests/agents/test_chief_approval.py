from proseforge.application.agents.approve_chief import ApprovalState
from proseforge.application.agents.chief_editor import create_chief_proposal

def test_chief_approval_is_user_bound_and_idempotent():
    state = ApprovalState(); proposal = create_chief_proposal(before="old", after="new", base_version_id="v1", rationale="r")
    first = state.approve("p", proposal, "old"); second = state.approve("p", proposal, "old")
    assert first.status == "APPROVED" and second.status == "APPROVED"
