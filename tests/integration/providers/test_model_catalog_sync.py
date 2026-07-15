import pytest

from proseforge.application.providers.model_catalog_service import InMemoryModelCatalog
from proseforge.domain.ports.model_provider import ProviderModel


class FakeProvider:
    provider_id = "fake"

    async def list_models(self):
        return [ProviderModel("fake", "future-model", "Future", {})]


@pytest.mark.asyncio
async def test_sync_adds_new_vendor_model_without_code_change():
    result = await InMemoryModelCatalog().sync(FakeProvider())
    assert result.added == ("future-model",)
