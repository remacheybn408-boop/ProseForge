from __future__ import annotations

from proseforge.domain.workflow.budget import budget_blocked


def budget_exceeded_after_usage(run: object) -> bool:
    return budget_blocked(
        used_tokens=int(getattr(run, "used_tokens", 0) or 0),
        token_limit=int(getattr(run, "token_limit", 0) or 0),
        estimated_next_tokens=0,
        estimated_cost=float(getattr(run, "estimated_cost", 0) or 0),
        cost_limit=float(getattr(run, "cost_limit", 0) or 0),
        estimated_next_cost=None,
    )
