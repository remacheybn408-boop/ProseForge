from dataclasses import dataclass

from proseforge.context_engine.budgeting import input_budget_for_model


@dataclass
class CatalogModel:
    context_window: int | None
    capabilities: dict[str, object]


def test_context_budget_uses_catalog_model_window():
    budget = input_budget_for_model(CatalogModel(200000, {}), requested_output=8192)

    assert budget > 128000


def test_context_budget_reads_capability_metadata_when_direct_window_is_missing():
    budget = input_budget_for_model(CatalogModel(None, {"context_window": 64000}), requested_output=4096)

    assert budget == 53504
