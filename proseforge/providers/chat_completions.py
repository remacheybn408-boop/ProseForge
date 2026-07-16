from __future__ import annotations

import json
from collections.abc import AsyncIterator

import httpx

from proseforge.domain.ports.model_provider import GenerationEvent, GenerationRequest, ModelProvider, ProviderModel


class ChatCompletionsProvider(ModelProvider):
    """Explicit OpenAI-compatible chat adapter used only by vendors that publish this contract."""

    provider_id = "compatible"
    default_base_url = ""
    auth_header = "Authorization"
    models_path = "/models"
    generation_path = "/chat/completions"

    def __init__(self, api_key: str = "", base_url: str | None = None, timeout: float = 30.0):
        self.base_url = (base_url or self.default_base_url).rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def headers(self) -> dict[str, str]:
        value = f"Bearer {self.api_key}" if self.auth_header.lower() == "authorization" else self.api_key
        return {self.auth_header: value, "Content-Type": "application/json"}

    async def validate_credentials(self) -> dict[str, object]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{self.models_path}", headers=self.headers)
            response.raise_for_status()
        return {"valid": True}

    async def list_models(self) -> list[ProviderModel]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{self.models_path}", headers=self.headers)
            response.raise_for_status()
        items = response.json().get("data", [])
        return [
            ProviderModel(self.provider_id, str(item["id"]), str(item.get("owned_by") or item["id"]), item.get("capabilities", {}))
            for item in items
            if item.get("id")
        ]

    async def count_tokens(self, request: GenerationRequest) -> int:
        return max(1, sum(len(str(block)) for block in (*request.system_blocks, *request.input_blocks)) // 2)

    async def stream(self, request: GenerationRequest) -> AsyncIterator[GenerationEvent]:
        messages = []
        for block in request.system_blocks:
            messages.append({"role": "system", "content": str(block.get("text", block.get("content", "")))})
        for block in request.input_blocks:
            messages.append({"role": str(block.get("role", "user")), "content": str(block.get("text", block.get("content", "")))})
        payload: dict[str, object] = {"model": request.model, "messages": messages, "stream": True}
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.top_p is not None:
            payload["top_p"] = request.top_p
        if request.max_output_tokens is not None:
            payload["max_tokens"] = request.max_output_tokens
        if request.response_schema is not None:
            payload["response_format"] = {"type": "json_schema", "json_schema": request.response_schema}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", f"{self.base_url}{self.generation_path}", headers=self.headers, json=payload) as response:
                response.raise_for_status()
                response_id = ""
                started = False
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        yield GenerationEvent("response.completed", data={"id": response_id})
                        continue
                    item = json.loads(raw)
                    response_id = str(item.get("id", response_id))
                    if not started:
                        started = True
                        yield GenerationEvent("response.started", data={"id": response_id})
                    for choice in item.get("choices", []):
                        delta = choice.get("delta", {})
                        text = delta.get("content", "") or ""
                        if text:
                            yield GenerationEvent("content.delta", text, {"id": response_id})
                    usage = item.get("usage")
                    if usage:
                        yield GenerationEvent("usage.updated", data=usage)
