from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PreparedChapterContext:
    project_id: str
    chapter_id: str
    chapter_no: int
    chapter_type: str
    context_text: str
    context_metadata: dict[str, object]
    context_hash: str


@dataclass(frozen=True)
class RuleQualityResult:
    status: str
    can_commit: bool
    blocked_by: tuple[str, ...]
    warnings: tuple[dict[str, object], ...]
    artifacts: tuple[str, ...]


@dataclass(frozen=True)
class CommitChapterResult:
    version_no: int
    content_hash: str
    word_count: int
    artifacts: tuple[str, ...]


class NovelEnginePort(Protocol):
    def prepare_chapter(
        self,
        *,
        legacy_slot: str,
        novel_slug: str,
        novel_title: str,
        volume_no: int,
        chapter_no: int,
        chapter_type: str,
    ) -> PreparedChapterContext: ...

    def run_rule_quality(
        self,
        *,
        legacy_slot: str,
        novel_slug: str,
        novel_title: str,
        volume_no: int,
        chapter_no: int,
        chapter_type: str,
        staged_file: str,
    ) -> RuleQualityResult: ...

    def commit_chapter(
        self,
        *,
        legacy_slot: str,
        novel_slug: str,
        novel_title: str,
        volume_no: int,
        chapter_no: int,
        chapter_type: str,
        staged_file: str,
    ) -> CommitChapterResult: ...
