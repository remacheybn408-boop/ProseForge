from __future__ import annotations

# Official docs: https://platform.openai.com/docs/api-reference
# Verified: 2026-07-15
# Model discovery: Models API
# Primary generation API: Responses API

import json
from collections.abc import AsyncIterator

import httpx

from proseforge.domain.ports.model_provider import GenerationEvent, GenerationRequest, ModelProvider, ProviderModel
from proseforge.providers.events import GenerationEventType


class OpenAIProvider(ModelProvider):
    provider_id = "openai"

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", timeout: float = 30.0):
        self._headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def validate_credentials(self) -> dict[str, object]:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}/models", headers=self._headers)
            response.raise_for_status()
            return {"valid": True}

    async def list_models(self) -> list[ProviderModel]:
        async with self._client() as client:
            response = await client.get(f"{self.base_url}/models", headers=self._headers)
            response.raise_for_status()
            return [ProviderModel("openai", item["id"], item.get("id", ""), {}) for item in response.json().get("data", [])]

    async def count_tokens(self, request: GenerationRequest) -> int:
        text = " ".join(str(block.get("text", "")) for block in (*request.system_blocks, *request.input_blocks))
        return max(1, len(text) // 2)

    async def stream(self, request: GenerationRequest) -> AsyncIterator[GenerationEvent]:
        payload: dict[str, object] = {
            "model": request.model,
            "stream": True,
            "input": [*request.system_blocks, *request.input_blocks],
        }
        for field in ("temperature", "top_p", "max_output_tokens"):
            value = getattr(request, field)
            if value is not None:
                payload[field] = value
        # 思考强度载荷按 catalog reasoning_parameter 的名字落到请求体顶层；
        # None（AUTO）时不多发任何字段，由 provider 默认值接管。
        if request.reasoning is not None:
            payload.update(request.reasoning)
        if request.response_schema is not None:
            payload["text"] = {"format": {"type": "json_schema", "schema": request.response_schema}}
        async with self._client().stream("POST", f"{self.base_url}/responses", headers=self._headers, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                event = json.loads(raw)
                yield self._normalize(event)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout)

    @staticmethod
    def _normalize(event: dict[str, object]) -> GenerationEvent:
        event_type = str(event.get("type", ""))
        mapping = {
            "response.created": GenerationEventType.RESPONSE_STARTED,
            "response.output_text.delta": GenerationEventType.CONTENT_DELTA,
            "response.completed": GenerationEventType.RESPONSE_COMPLETED,
            "response.done": GenerationEventType.RESPONSE_COMPLETED,
            "response.failed": GenerationEventType.RESPONSE_FAILED,
            "response.usage.updated": GenerationEventType.USAGE_UPDATED,
        }
        normalized = mapping.get(event_type, GenerationEventType.RESPONSE_FAILED)
        text = str(event.get("delta", ""))
        data = {key: value for key, value in event.items() if key not in {"type", "delta"}}
        return GenerationEvent(normalized.value, text=text, data=data)
