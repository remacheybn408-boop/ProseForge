import pytest

from proseforge.domain.ports.model_provider import GenerationRequest, ProviderModel
from proseforge.providers.capabilities import ModelCapabilityError, validate_request


def test_capability_error_lists_exact_missing_features():
    model = ProviderModel("fake", "m", "M", {"reasoning": False})
    request = GenerationRequest("m", (), (), response_schema={}, reasoning={})
    with pytest.raises(ModelCapabilityError) as error:
        validate_request(model, request)
    assert error.value.missing == ("structured_output", "reasoning")


def test_capability_error_reports_modality_and_context_overflow():
    model = ProviderModel("fake", "m", "M", {"input_modalities": ("text",)}, context_window=4)
    request = GenerationRequest("m", (), ({"role": "user", "text": "a very long prompt"},), max_output_tokens=2)
    with pytest.raises(ModelCapabilityError) as error:
        validate_request(model, request)
    assert error.value.missing == ("context_window",)


def test_capability_error_reports_unsupported_input_modality():
    model = ProviderModel("fake", "m", "M", {"input_modalities": ("text",)})
    request = GenerationRequest("m", (), ({"type": "image", "url": "x"},))
    with pytest.raises(ModelCapabilityError) as error:
        validate_request(model, request)
    assert error.value.missing == ("input_modality:image",)
