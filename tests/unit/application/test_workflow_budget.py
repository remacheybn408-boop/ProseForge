from types import SimpleNamespace

from proseforge.application.workflows.budget import budget_exceeded_after_usage


def test_workflow_budget_is_checked_after_provider_usage_is_recorded():
    assert budget_exceeded_after_usage(SimpleNamespace(used_tokens=101, token_limit=100, estimated_cost=0, cost_limit=0)) is True
    assert budget_exceeded_after_usage(SimpleNamespace(used_tokens=99, token_limit=100, estimated_cost=0, cost_limit=0)) is False
