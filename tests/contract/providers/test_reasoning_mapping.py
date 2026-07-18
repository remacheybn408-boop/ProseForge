"""Provider 特定的思考强度映射（V2-004）。

catalog `reasoning_parameter` 决定载荷形状：OpenAI reasoning_effort /
Anthropic thinking / Google thinking_budget；其它参数名按 strength 透传。
不支持的级别抛 ValueError（路由层转 422 + supported_levels），绝不静默降级。
"""

import pytest

from proseforge.application.models.reasoning_policy import resolve_reasoning
from proseforge.domain.model.capabilities import ModelCapabilities


def _caps(parameter: str | None, *, max_output: int = 4096) -> ModelCapabilities:
    return ModelCapabilities(128000, max_output, True, parameter, False, False, "catalog")


def test_openai_reasoning_effort_maps_levels_to_effort_words():
    caps = _caps("reasoning_effort")

    assert resolve_reasoning("fast", caps)["provider_parameter"] == {"reasoning_effort": "low"}
    assert resolve_reasoning("standard", caps)["provider_parameter"] == {"reasoning_effort": "medium"}
    assert resolve_reasoning("deep", caps)["provider_parameter"] == {"reasoning_effort": "high"}


def test_openai_max_clamps_to_high_and_records_warning():
    policy = resolve_reasoning("max", _caps("reasoning_effort"))

    assert policy["provider_parameter"] == {"reasoning_effort": "high"}
    assert policy["warnings"], "clamping must be recorded, never silent"


def test_anthropic_thinking_maps_to_budget_tokens():
    policy = resolve_reasoning("deep", _caps("thinking", max_output=4096))

    assert policy["provider_parameter"] == {"thinking": {"type": "enabled", "budget_tokens": int(0.75 * 4096)}}


def test_anthropic_thinking_budget_respects_provider_minimum():
    policy = resolve_reasoning("fast", _caps("thinking", max_output=1024))

    assert policy["provider_parameter"] == {"thinking": {"type": "enabled", "budget_tokens": 1024}}


def test_google_thinking_budget_maps_to_integer_tokens():
    policy = resolve_reasoning("standard", _caps("thinking_budget", max_output=4096))

    assert policy["provider_parameter"] == {"thinking_budget": int(0.5 * 4096)}


def test_unknown_parameter_passes_strength_through():
    policy = resolve_reasoning("deep", _caps("effort"))

    assert policy["provider_parameter"] == {"effort": 0.75}
    assert policy["parameter"] == "effort"


def test_auto_never_claims_a_provider_parameter():
    policy = resolve_reasoning("auto", _caps("reasoning_effort"))

    assert policy["parameter"] is None
    assert policy["provider_parameter"] is None


def test_unsupported_level_raises_instead_of_silent_downgrade():
    caps = ModelCapabilities(8192, 1024, False, None, False, False, "fallback")

    with pytest.raises(ValueError, match="unsupported"):
        resolve_reasoning("max", caps)
    with pytest.raises(ValueError, match="unsupported"):
        resolve_reasoning("fast", caps)
