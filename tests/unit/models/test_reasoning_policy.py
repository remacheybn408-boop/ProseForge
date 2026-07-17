import pytest

from proseforge.application.models.reasoning_policy import resolve_reasoning
from proseforge.domain.model.capabilities import ModelCapabilities


def test_auto_does_not_claim_deep_reasoning():
    caps = ModelCapabilities(8192, 1024, False, None, False, False, "catalog")
    assert resolve_reasoning("auto", caps)["parameter"] is None
    with pytest.raises(ValueError, match="unsupported"):
        resolve_reasoning("max", caps)
