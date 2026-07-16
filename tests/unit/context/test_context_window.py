from __future__ import annotations

from dataclasses import dataclass

from proseforge.api.routes.context import resolve_context_window


@dataclass
class CatalogModel:
    context_window: int | None
    capabilities: dict[str, object]


def test_context_window_uses_catalog_metadata_before_fallback():
    assert resolve_context_window(CatalogModel(200000, {})) == 200000
    assert resolve_context_window(CatalogModel(None, {"context_window": 64000})) == 64000
    assert resolve_context_window(None) == 128000
