from __future__ import annotations

from dataclasses import dataclass

from proseforge.api.routes.context import context_budget, resolve_context_window


@dataclass
class CatalogModel:
    context_window: int | None
    capabilities: dict[str, object]
    max_output_tokens: int | None = None


def test_context_window_uses_catalog_metadata_before_fallback():
    assert resolve_context_window(CatalogModel(200000, {})) == 200000
    assert resolve_context_window(CatalogModel(None, {"context_window": 64000})) == 64000
    assert resolve_context_window(None) == 128000


def test_context_budget_reserves_model_output_without_mixing_historical_usage():
    budget = context_budget(CatalogModel(20000, {}, max_output_tokens=4000), used_tokens=5000)

    assert budget == {
        "context_window": 20000,
        "used_tokens": 5000,
        "system_reserved_tokens": 0,
        "history_tokens": 0,
        "output_reserve_tokens": 4000,
        "available_tokens": 11000,
    }
