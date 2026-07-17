from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ReasoningLevel(str, Enum):
    AUTO = "auto"
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
    MAX = "max"


@dataclass(frozen=True)
class ModelCapabilities:
    context_window: int
    max_output_tokens: int
    supports_reasoning: bool
    reasoning_parameter: str | None
    supports_tools: bool
    supports_vision: bool
    source: Literal["catalog", "provider", "user", "fallback"]


def capabilities_from_model(model) -> ModelCapabilities:
    raw = model.capabilities or {}
    return ModelCapabilities(int(model.context_window or raw.get("context_window", 8192)), int(model.max_output_tokens or raw.get("max_output_tokens", 1024)), bool(raw.get("reasoning", False)), str(raw.get("reasoning_parameter")) if raw.get("reasoning_parameter") else None, bool(raw.get("tools", False)), bool(raw.get("vision", False)), "catalog")
