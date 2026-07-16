from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NovelWorkflowResult:
    status: str
    completed_chapters: tuple[int, ...]
    failed_chapter: int | None = None


class NovelWorkflowService:
    def __init__(self, chapter_runner):
        self.chapter_runner = chapter_runner
        self.completed: set[int] = set()
        self.paused = False
        self.cancelled = False
        self.pause_after_current = False

    def pause(self, after_current: bool = False) -> None:
        self.pause_after_current = after_current
        if not after_current:
            self.paused = True

    def resume(self) -> None:
        self.paused = False
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    async def run(self, chapter_numbers: list[int]) -> NovelWorkflowResult:
        for chapter_no in chapter_numbers:
            if chapter_no in self.completed:
                continue
            if self.cancelled:
                return NovelWorkflowResult("CANCELLED", tuple(sorted(self.completed)))
            if self.paused:
                return NovelWorkflowResult("PAUSED", tuple(sorted(self.completed)))
            try:
                result = self.chapter_runner(chapter_no)
                if hasattr(result, "__await__"):
                    result = await result
                if getattr(result, "status", result if isinstance(result, str) else "PASS") != "PASS":
                    return NovelWorkflowResult("FAILED", tuple(sorted(self.completed)), chapter_no)
                self.completed.add(chapter_no)
            except Exception:
                return NovelWorkflowResult("FAILED", tuple(sorted(self.completed)), chapter_no)
            if self.pause_after_current:
                self.paused = True
                self.pause_after_current = False
                return NovelWorkflowResult("PAUSED", tuple(sorted(self.completed)))
        return NovelWorkflowResult("COMPLETED", tuple(sorted(self.completed)))
