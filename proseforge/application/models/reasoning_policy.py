"""思考强度策略（V2-002 引入，V2-004 真实化 provider 参数映射）。

级别 → provider 参数载荷按 catalog 的 ``reasoning_parameter`` 映射：
- OpenAI    ``reasoning_effort`` → ``{"reasoning_effort": "low|medium|high"}``
- Anthropic ``thinking``         → ``{"thinking": {"type": "enabled", "budget_tokens": N}}``
- Google    ``thinking_budget``  → ``{"thinking_budget": N}``

其它参数名按 ``{"<parameter>": strength}`` 透传。不支持的级别抛
ValueError（路由层转 422 + supported_levels），绝不静默降级为 auto；
max 被钳到 provider 上限时记入 warnings。

Anthropic 要求 ``budget_tokens >= 1024`` 且严格小于 ``max_tokens``：预算钳到
``max_output_tokens - 1``；若 ``max_output_tokens <= 1024``（合法窗口为空），
不静默降级——``provider_parameter`` 返回 None（不发 thinking）并记 warning。
"""

from __future__ import annotations

from proseforge.domain.model.capabilities import ReasoningLevel

_STRENGTH = {ReasoningLevel.FAST: 0.25, ReasoningLevel.STANDARD: 0.5, ReasoningLevel.DEEP: 0.75, ReasoningLevel.MAX: 1.0}
_EFFORT_WORDS = {ReasoningLevel.FAST: "low", ReasoningLevel.STANDARD: "medium", ReasoningLevel.DEEP: "high", ReasoningLevel.MAX: "high"}
# Anthropic thinking budget_tokens 的 provider 下限。
_ANTHROPIC_MIN_THINKING_BUDGET = 1024


def resolve_reasoning(level: ReasoningLevel | str, capabilities) -> dict[str, object]:
    selected = ReasoningLevel(level)
    if selected is not ReasoningLevel.AUTO and not capabilities.supports_reasoning:
        raise ValueError(f"reasoning level {selected.value} is unsupported; use auto")
    if selected is ReasoningLevel.AUTO:
        return {"level": selected.value, "parameter": None, "provider_parameter": None, "warnings": []}
    strength = _STRENGTH[selected]
    parameter = capabilities.reasoning_parameter or "reasoning"
    warnings: list[str] = []
    provider_parameter = _provider_parameter(parameter, strength, selected, capabilities, warnings)
    return {"level": selected.value, "parameter": parameter, "strength": strength, "provider_parameter": provider_parameter, "warnings": warnings}


def _provider_parameter(parameter: str, strength: float, selected: ReasoningLevel, capabilities, warnings: list[str]) -> dict[str, object] | None:
    if parameter == "reasoning_effort":
        if selected is ReasoningLevel.MAX:
            warnings.append("reasoning level 'max' is clamped to the provider's maximum effort 'high'")
        return {"reasoning_effort": _EFFORT_WORDS[selected]}
    if parameter == "thinking":
        if capabilities.max_output_tokens <= _ANTHROPIC_MIN_THINKING_BUDGET:
            # budget_tokens 须 ≥ 1024 且 < max_tokens，二者不可兼得——显式关闭
            # thinking 并记 warning，绝不发出 provider 必拒的载荷。
            warnings.append("thinking disabled: max_output_tokens below provider minimum")
            return None
        budget = max(_ANTHROPIC_MIN_THINKING_BUDGET, int(strength * capabilities.max_output_tokens))
        budget = min(budget, capabilities.max_output_tokens - 1)
        return {"thinking": {"type": "enabled", "budget_tokens": budget}}
    if parameter == "thinking_budget":
        return {"thinking_budget": max(1, int(strength * capabilities.max_output_tokens))}
    return {parameter: strength}
