from __future__ import annotations

import hashlib
import json
from pathlib import Path

from proseforge.domain.ports.novel_engine import (
    CommitChapterResult,
    NovelEnginePort,
    PreparedChapterContext,
    RuleQualityResult,
)
from src.application.pipeline_service import PipelineService, PreChapterRequest


class LegacyNovelEngineAdapter(NovelEnginePort):
    """Explicit, single-entry adapter around the legacy chapter engine."""

    def __init__(self, *, project_root: str | Path):
        self.project_root = Path(project_root).expanduser().resolve()

    def _state_path(self, chapter_no: int) -> Path:
        return self.project_root / "exports" / "pipeline_state" / f"chapter_{chapter_no:03d}_state.json"

    def prepare_chapter(
        self,
        *,
        legacy_slot: str,
        novel_slug: str,
        novel_title: str,
        volume_no: int,
        chapter_no: int,
        chapter_type: str,
    ) -> PreparedChapterContext:
        result = PipelineService().pre(PreChapterRequest(
            project_root=self.project_root,
            slot_id=legacy_slot,
            novel_slug=novel_slug,
            novel_title=novel_title,
            volume_no=volume_no,
            chapter_no=chapter_no,
            chapter_type=chapter_type,
        ))
        context_text = json.dumps(result, ensure_ascii=False, sort_keys=True)
        return PreparedChapterContext(
            project_id=legacy_slot,
            chapter_id=f"{legacy_slot}:{chapter_no}",
            chapter_no=chapter_no,
            chapter_type=chapter_type,
            context_text=context_text,
            context_metadata={"legacy_slot": legacy_slot},
            context_hash=hashlib.sha256(context_text.encode("utf-8")).hexdigest(),
        )

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
    ) -> RuleQualityResult:
        state_path = self._state_path(chapter_no)
        if not state_path.exists():
            return RuleQualityResult(
                status="BLOCKED",
                can_commit=False,
                blocked_by=("pre_state_missing",),
                warnings=(),
                artifacts=(),
            )
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return RuleQualityResult(
                status="ERROR",
                can_commit=False,
                blocked_by=(f"pre_state_invalid:{exc}",),
                warnings=(),
                artifacts=(),
            )
        if not state.get("pre_done") or not state.get("allowed_to_write"):
            return RuleQualityResult(
                status="BLOCKED",
                can_commit=False,
                blocked_by=("pre_state_incomplete",),
                warnings=(),
                artifacts=(),
            )
        return RuleQualityResult(
            status="PASS",
            can_commit=True,
            blocked_by=(),
            warnings=(),
            artifacts=(str(staged_file),),
        )

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
    ) -> CommitChapterResult:
        quality = self.run_rule_quality(
            legacy_slot=legacy_slot,
            novel_slug=novel_slug,
            novel_title=novel_title,
            volume_no=volume_no,
            chapter_no=chapter_no,
            chapter_type=chapter_type,
            staged_file=staged_file,
        )
        if not quality.can_commit:
            raise RuntimeError("chapter commit blocked: " + ",".join(quality.blocked_by))
        content = Path(staged_file).read_text(encoding="utf-8")
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        return CommitChapterResult(
            version_no=0,
            content_hash=digest,
            word_count=len(content),
            artifacts=(staged_file,),
        )
