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
        for key in unavailable:
            current = self.models[(provider.provider_id, key)]
            self.models[(provider.provider_id, key)] = ProviderModel(
                current.provider,
                current.model_id,
                current.display_name,
                {**current.capabilities, "availability": "unavailable"},
                current.context_window,
                current.max_output_tokens,
            )
        for key, model in incoming.items():
            self.models[key] = ProviderModel(
                model.provider,
                model.model_id,
                model.display_name,
                {**model.capabilities, "availability": "available"},
                model.context_window,
                model.max_output_tokens,
            )
        return CatalogSyncResult(added, unavailable)
