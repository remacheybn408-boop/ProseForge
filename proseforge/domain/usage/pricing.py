from __future__ import annotations

from proseforge.domain.usage.normalization import UsageDelta


def calculate_cost_usd(delta: UsageDelta, prices: dict[str, object] | None) -> float | None:
    if not prices:
        return None

    def amount(name: str) -> float:
        try:
            return float(prices.get(name, 0) or 0)
        except (TypeError, ValueError):
            return 0.0

    return (
        delta.input_tokens * amount("input_price_per_million")
        + delta.output_tokens * amount("output_price_per_million")
        + delta.cached_input_tokens * amount("cached_input_price_per_million")
    ) / 1_000_000
