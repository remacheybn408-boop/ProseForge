import pytest

from proseforge.domain.ports.model_provider import GenerationRequest, ProviderModel
from proseforge.providers.capabilities import ModelCapabilityError, validate_request


def test_capability_error_lists_exact_missing_features():
    model = ProviderModel("fake", "m", "M", {"reasoning": False})
    request = GenerationRequest("m", (), (), response_schema={}, reasoning={})
    with pytest.raises(ModelCapabilityError) as error:
        validate_request(model, request)
    assert error.value.missing == ("structured_output", "reasoning")
