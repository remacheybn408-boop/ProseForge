import pytest

from proseforge.domain.workflow.state import InvalidWorkflowTransition, WorkflowState


def test_completed_cannot_restart():
    state = WorkflowState("COMPLETED")
    with pytest.raises(InvalidWorkflowTransition):
        state.transition("RUNNING")


def test_running_can_become_budget_blocked_after_usage():
    state = WorkflowState("RUNNING")
    state.transition("BUDGET_BLOCKED")
    assert state.status == "BUDGET_BLOCKED"
