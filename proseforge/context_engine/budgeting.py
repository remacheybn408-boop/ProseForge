from dataclasses import dataclass


@dataclass(frozen=True)
class ContextBudget:
    context_window: int
    input_tokens: int
    output_reserve: int
    provider_reserved: int


def resolve_context_window(model: object | None, fallback: int = 128000) -> int:
    if model is None:
        return fallback
    direct = getattr(model, "context_window", None)
    if isinstance(direct, int) and direct > 0:
        return direct
    capabilities = getattr(model, "capabilities", {})
    if isinstance(capabilities, dict):
        value = capabilities.get("context_window")
        if isinstance(value, int) and value > 0:
            return value
    return fallback


def calculate_budget(context_window: int, requested_output: int, provider_reserved: int = 0, safety_margin_ratio: float = 0.1) -> ContextBudget:
    margin = int(context_window * safety_margin_ratio)
    return ContextBudget(context_window, max(0, context_window - requested_output - provider_reserved - margin), requested_output, provider_reserved)


def input_budget_for_model(model: object | None, *, requested_output: int, provider_reserved: int = 0) -> int:
    return calculate_budget(
        resolve_context_window(model),
        requested_output=requested_output,
        provider_reserved=provider_reserved,
    ).input_tokens
