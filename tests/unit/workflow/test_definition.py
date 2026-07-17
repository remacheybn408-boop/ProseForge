import pytest
from proseforge.domain.workflow.definition import WorkflowDefinition, WorkflowNode


def test_definition_rejects_unknown_edges():
    definition = WorkflowDefinition("w", 1, (WorkflowNode("intake", "intake", "Intake"),), (("intake", "missing"),))
    with pytest.raises(ValueError, match="unknown"):
        definition.validate()
