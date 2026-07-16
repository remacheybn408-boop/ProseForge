from __future__ import annotations

from typing import Any

from proseforge.domain.usage import UsageDelta, normalize_usage


def normalize_provider_usage(provider: str, data: dict[str, object], *, estimated: bool = False, final: bool = False) -> UsageDelta:
    payload: dict[str, Any] = dict(data)
    metadata = payload.get("usageMetadata")
    if isinstance(metadata, dict):
        payload["usage"] = {
            "input_tokens": metadata.get("promptTokenCount", 0),
            "output_tokens": metadata.get("candidatesTokenCount", 0),
            "cached_input_tokens": metadata.get("cachedContentTokenCount", 0),
            "reasoning_tokens": metadata.get("thoughtsTokenCount", 0),
            "total_tokens": metadata.get("totalTokenCount"),
        }
    elif provider in {"ollama", "vllm"} and "usage" not in payload:
        payload["usage"] = {"input_tokens": payload.get("prompt_eval_count", 0), "output_tokens": payload.get("eval_count", 0)}
    elif provider == "cohere" and "usage" not in payload:
        billed = payload.get("billed_units") if isinstance(payload.get("billed_units"), dict) else payload
        payload["usage"] = {"input_tokens": billed.get("input_tokens", 0), "output_tokens": billed.get("output_tokens", 0)}
    return normalize_usage(payload, source="estimated" if estimated else "provider", final=final)
