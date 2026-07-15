import pytest

from proseforge.application.providers.model_catalog_service import InMemoryModelCatalog
from proseforge.domain.ports.model_provider import ProviderModel


class FakeProvider:
    provider_id = "fake"

    async def list_models(self):
        return [ProviderModel("fake", "future-model", "Future", {})]


@pytest.mark.asyncio
async def test_sync_adds_new_vendor_model_without_code_change():
    catalog = InMemoryModelCatalog()
    result = await catalog.sync(FakeProvider())
    assert result.added == ("future-model",)
    assert catalog.models[("fake", "future-model")].capabilities["availability"] == "available"


@pytest.mark.asyncio
async def test_sync_marks_missing_vendor_model_unavailable_without_deleting_it():
    catalog = InMemoryModelCatalog()
    catalog.models[("fake", "old-model")] = ProviderModel("fake", "old-model", "Old", {})
    result = await catalog.sync(FakeProvider())
    assert result.unavailable == ("old-model",)
    assert catalog.models[("fake", "old-model")].capabilities["availability"] == "unavailable"
