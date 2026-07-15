from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from proseforge.domain.ports.model_provider import GenerationEvent, GenerationRequest, ModelProvider, ProviderModel


class HttpJsonProvider(ModelProvider):
    provider_id = "custom"
    models_path = "/models"
    generation_path = "/responses"

    def __init__(self, api_key: str = "", base_url: str = "", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.timeout = timeout

    async def validate_credentials(self) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{self.models_path}", headers=self._headers)
            response.raise_for_status()
        return {"valid": True}

    async def list_models(self) -> list[ProviderModel]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{self.models_path}", headers=self._headers)
            response.raise_for_status()
        return [ProviderModel(self.provider_id, item["id"], item.get("display_name", item["id"]), item.get("capabilities", {})) for item in response.json().get("data", [])]

    async def count_tokens(self, request: GenerationRequest) -> int:
        return max(1, sum(len(str(block)) for block in (*request.system_blocks, *request.input_blocks)) // 2)

    async def stream(self, request: GenerationRequest) -> AsyncIterator[GenerationEvent]:
        payload = {"model": request.model, "input": [*request.system_blocks, *request.input_blocks], "stream": True}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}{self.generation_path}", headers=self._headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data:") and line[5:].strip() != "[DONE]":
                        item = json.loads(line[5:].strip())
                        yield GenerationEvent(str(item.get("type", "content.delta")), str(item.get("delta", "")), item)
