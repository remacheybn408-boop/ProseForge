from __future__ import annotations


def aggregate_usage(records) -> dict[str, dict[str, int | float | None]]:
    buckets = {
        "actual": {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0, "cost_usd": None},
        "estimated": {"input_tokens": 0, "output_tokens": 0, "cached_input_tokens": 0, "reasoning_tokens": 0, "total_tokens": 0, "cost_usd": None},
    }
    for row in records:
        bucket = buckets["actual" if row.usage_source == "provider" else "estimated"]
        for field in ("input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "total_tokens"):
            bucket[field] += int(getattr(row, field, 0) or 0)
        if row.cost_usd is not None:
            bucket["cost_usd"] = float(bucket["cost_usd"] or 0) + float(row.cost_usd)
    return buckets


class UsageQuery:
    def __init__(self, repository):
        self.repository = repository

    async def records(self, user_id: str, **filters):
        return await self.repository.list_for_user(user_id, **filters)

    async def summary(self, user_id: str, **filters):
        rows = await self.records(user_id, **filters)
        return aggregate_usage(rows)
