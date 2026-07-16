from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterGenerationResult:
    status: str
    content: str
    rewrite_rounds: int
    quality: object
    commit_result: object | None = None


class ChapterService:
    def __init__(self, writer, quality_service, model_review, rewriter, committer=None, max_rewrites: int = 2):
        self.writer = writer
        self.quality_service = quality_service
        self.model_review = model_review
        self.rewriter = rewriter
        self.committer = committer
        self.max_rewrites = max_rewrites

    async def generate(self, request: object, context: dict | None = None) -> ChapterGenerationResult:
        context = context or {}
        content = await self._maybe_await(self.writer(request, context))
        rounds = 0
        while True:
            rule = self.quality_service.run(content, context.get("chapter_no", 0), context)
            if rule.status == "BLOCK":
                return ChapterGenerationResult("BLOCK", content, rounds, rule)
            reviewer = self.model_review.review if hasattr(self.model_review, "review") else self.model_review
            review = await self._maybe_await(reviewer(content, context))
            if str(review.get("status", "PASS")).upper() == "PASS":
                commit = await self._maybe_await(self.committer(content, context)) if self.committer else None
                return ChapterGenerationResult("PASS", content, rounds, rule, commit)
            if rounds >= self.max_rewrites:
                return ChapterGenerationResult("BLOCK", content, rounds, rule)
            content = await self._maybe_await(self.rewriter(content, review, context))
            rounds += 1

    @staticmethod
    async def _maybe_await(value):
        if hasattr(value, "__await__"):
            return await value
        return value
