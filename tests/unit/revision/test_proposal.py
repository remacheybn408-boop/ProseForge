import pytest

from proseforge.application.revision.approve_proposal import approve_proposal
from proseforge.application.revision.create_proposal import create_proposal
from proseforge.application.revision.reject_proposal import reject_proposal


def test_proposal_requires_fresh_base_and_never_mutates_source():
    proposal = create_proposal(base_version_id="v1", before="old", after="new", rationale="clarity")
    assert approve_proposal(proposal, "old").status == "APPROVED"
    assert reject_proposal(proposal).status == "REJECTED"
    with pytest.raises(ValueError, match="stale"):
        approve_proposal(proposal, "changed")
