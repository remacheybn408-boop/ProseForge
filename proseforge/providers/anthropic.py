from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from proseforge.domain.ports.model_provider import (
    GenerationEvent,
    GenerationRequest,
    ModelProvider,
    ProviderModel,
)


class AnthropicProvider(ModelProvider):
    """Native Anthropic Messages API adapter."""

    provider_id = "anthropic"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.anthropic.com/v1",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        self.timeout = timeout

    async def validate_credentials(self) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/models", headers=self._headers)
            response.raise_for_status()
        return {"valid": True}

    async def list_models(self) -> list[ProviderModel]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/models", headers=self._headers)
            response.raise_for_status()
        return [
            ProviderModel(
                self.provider_id,
                item["id"],
                item.get("display_name", item["id"]),
                {},
            )
            for item in response.json().get("data", [])
        ]

    async def count_tokens(self, request: GenerationRequest) -> int:
        return max(
            1,
            sum(
                len(str(block.get("text", block.get("content", ""))))
                for block in (*request.system_blocks, *request.input_blocks)
            )
            // 2,
        )

    async def stream(self, request: GenerationRequest) -> AsyncIterator[GenerationEvent]:
        system = "\n".join(str(block.get("text", "")) for block in request.system_blocks)
        messages = [
            {
                "role": str(block.get("role", "user")),
                "content": str(block.get("text", block.get("content", ""))),
            }
            for block in request.input_blocks
        ]
        payload: dict[str, object] = {
            "model": request.model,
            "max_tokens": request.max_output_tokens or 4096,
            "messages": messages,
            "stream": True,
        }
        if system:
            payload["system"] = system
        for field in ("temperature", "top_p"):
            value = getattr(request, field)
            if value is not None:
                payload[field] = value
        # 思考强度载荷按 catalog reasoning_parameter 的名字落到请求体顶层；
        # None（AUTO）时不多发任何字段，由 provider 默认值接管。
        if request.reasoning is not None:
            payload.update(request.reasoning)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}/messages", headers=self._headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = json.loads(line[5:].strip())
                    text = (
                        str(data.get("delta", {}).get("text", ""))
                        if isinstance(data.get("delta"), dict)
                        else ""
                    )
                    event_type = "content.delta" if text else str(data.get("type", "message.delta"))
                    yield GenerationEvent(event_type, text, data)
