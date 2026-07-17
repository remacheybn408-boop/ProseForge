from __future__ import annotations

from proseforge.domain.model.capabilities import capabilities_from_model
from proseforge.application.models.reasoning_policy import resolve_reasoning


def resolve_model(model, reasoning: str = "auto") -> dict[str, object]:
    capabilities = capabilities_from_model(model)
    policy = resolve_reasoning(reasoning, capabilities)
    return {"provider": model.provider, "model_id": model.model_id, "capabilities": capabilities, "reasoning": policy}
