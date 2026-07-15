"""Stable application boundary for chapter pipeline operations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.runtime import build_pipeline_context


@dataclass(frozen=True)
class PreChapterRequest:
    project_root: str | Path
    novel_slug: str
    chapter_no: int
    novel_title: str = ""
    volume_no: int = 1
    chapter_type: str = "normal"
    config_path: str | Path | None = None
    slot_id: str | None = None


@dataclass(frozen=True)
class PostChapterRequest:
    project_root: str | Path
    novel_slug: str
    chapter_no: int
    novel_title: str = ""
    volume_no: int = 1
    chapter_type: str = "normal"
    merge_if_short: bool = False
    config_path: str | Path | None = None
    slot_id: str | None = None


class PipelineService:
    """Application-level orchestration independent of an agent or CLI."""

    @staticmethod
    def _context(*, project_root, novel_slug, novel_title, volume_no, config_path, slot_id):
        return build_pipeline_context(
            project_root=project_root,
            config_path=config_path,
            novel_slug=novel_slug,
            novel_title=novel_title,
            volume_no=volume_no,
            slot_id=slot_id,
        )

    def pre(self, request: PreChapterRequest) -> dict:
        from src.pipeline.pre import run_pre
        context = self._context(
            project_root=request.project_root,
            novel_slug=request.novel_slug,
            novel_title=request.novel_title,
            volume_no=request.volume_no,
            config_path=request.config_path,
            slot_id=request.slot_id,
        )
        return run_pre(
            chapter_no=request.chapter_no,
            chapter_type=request.chapter_type,
            novel_slug=request.novel_slug,
            novel_title=request.novel_title,
            volume_no=request.volume_no,
            context=context,
        )

    def post(self, request: PostChapterRequest) -> dict | None:
        from src.pipeline.post import run_post
        context = self._context(
            project_root=request.project_root,
            novel_slug=request.novel_slug,
            novel_title=request.novel_title,
            volume_no=request.volume_no,
            config_path=request.config_path,
            slot_id=request.slot_id,
        )
        return run_post(
            chapter_no=request.chapter_no,
            chapter_type=request.chapter_type,
            novel_slug=request.novel_slug,
            novel_title=request.novel_title,
            volume_no=request.volume_no,
            merge_if_short=request.merge_if_short,
            context=context,
        )
