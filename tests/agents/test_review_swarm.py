from proseforge.application.agents.review_swarm import Finding, detect_conflicts, review_supported
from proseforge.application.agents.chief_editor import create_chief_proposal

def test_review_conflicts_are_retained_and_chief_only_proposes():
    left = Finding("a", "keep", "line-1"); right = Finding("b", "remove", "line-1")
    assert detect_conflicts([left, right]) == [(left, right)]; assert not review_supported(Finding("a", "unsupported", None))
    proposal = create_chief_proposal(before="old", after="new", base_version_id="v1", rationale="merge"); assert proposal.status == "PROPOSED"
