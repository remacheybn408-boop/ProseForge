from proseforge.domain.usage import UsageDelta
from proseforge.domain.usage.pricing import calculate_cost_usd


def test_pricing_uses_model_catalog_rates_and_keeps_unknown_cost_null():
    delta = UsageDelta(input_tokens=1_000_000, output_tokens=500_000, total_tokens=1_500_000)

    assert calculate_cost_usd(delta, {"input_price_per_million": 1.0, "output_price_per_million": 2.0}) == 2.0
    assert calculate_cost_usd(delta, None) is None
