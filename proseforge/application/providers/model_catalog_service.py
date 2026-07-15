from __future__ import annotations

from dataclasses import dataclass

from proseforge.domain.ports.model_provider import ModelProvider, ProviderModel


@dataclass(frozen=True)
class CatalogSyncResult:
    added: tuple[str, ...]
    unavailable: tuple[str, ...] = ()
    error: str | None = None


class InMemoryModelCatalog:
    def __init__(self) -> None:
        self.models: dict[tuple[str, str], ProviderModel] = {}
        self.manual: set[tuple[str, str]] = set()

    async def sync(self, provider: ModelProvider) -> CatalogSyncResult:
        try:
            discovered = await provider.list_models()
        except Exception as exc:
            return CatalogSyncResult((), error=type(exc).__name__)
        incoming = {(item.provider, item.model_id): item for item in discovered}
        added = tuple(sorted(key[1] for key in incoming if key not in self.models))
        unavailable = tuple(sorted(key[1] for key in self.models if key[0] == provider.provider_id and key not in incoming and key not in self.manual))
        self.models.update(incoming)
        return CatalogSyncResult(added, unavailable)
