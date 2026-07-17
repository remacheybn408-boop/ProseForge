from __future__ import annotations

from proseforge.domain.model.capabilities import ReasoningLevel


def resolve_reasoning(level: ReasoningLevel | str, capabilities) -> dict[str, object]:
    selected = ReasoningLevel(level)
    if selected is not ReasoningLevel.AUTO and not capabilities.supports_reasoning:
        raise ValueError(f"reasoning level {selected.value} is unsupported; use auto")
    if selected is ReasoningLevel.AUTO:
        return {"level": selected.value, "parameter": None, "warnings": []}
    scale = {ReasoningLevel.FAST: 0.25, ReasoningLevel.STANDARD: 0.5, ReasoningLevel.DEEP: 0.75, ReasoningLevel.MAX: 1.0}
    return {"level": selected.value, "parameter": capabilities.reasoning_parameter or "reasoning", "strength": scale[selected], "warnings": []}
