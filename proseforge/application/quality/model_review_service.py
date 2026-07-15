from __future__ import annotations


class ModelReviewService:
    def __init__(self, reviewer):
        self.reviewer = reviewer

    async def review(self, content: str, context: dict | None = None) -> dict[str, object]:
        result = self.reviewer(content, context or {})
        if hasattr(result, "__await__"):
            result = await result
        return result
