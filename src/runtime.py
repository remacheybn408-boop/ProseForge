#!/usr/bin/env python3
"""Unified runtime/path/context helpers for ProseForge."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.utils.config_utils import (
    find_project_root,
    load_json_config,
    resolve_path,
)


@dataclass(frozen=True)
class ProjectPaths:
    project_root: Path
    config_path: Path | None
    workspace_root: Path
    registry_path: Path


@dataclass
class PipelineContext:
    project_root: Path
    config_path: Path | None
    cfg: dict[str, Any]
    novel_slug: str
    novel_title: str
    volume_no: int
    db_path: Path
    novels_root: Path
    exports_root: Path
    reports_root: Path
    outputs_root: Path
    tmp_root: Path
    workspace_root: Path
    active_slot: str
    chapters_dir: Path
    state_dir: Path
    wc_rules: dict[str, Any]
    wc_default: dict[str, Any]
    allow_short_chapter: bool
    min_scenes: int


def build_project_paths(
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> ProjectPaths:
    root = find_project_root(project_root)
    resolved_config = None
    if config_path:
        candidate = Path(config_path)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved_config = candidate
    workspace_root = root / "workspace"
    return ProjectPaths(
        project_root=root,
        config_path=resolved_config,
        workspace_root=workspace_root,
        registry_path=workspace_root / "registry.json",
    )


def _load_registry(paths: ProjectPaths) -> dict[str, Any]:
    if not paths.registry_path.exists():
        return {}
    try:
        payload = json.loads(paths.registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _resolve_slot_word_count(paths: ProjectPaths, active_slot: str) -> dict[str, Any] | None:
    if not active_slot:
        return None
    project_file = paths.workspace_root / active_slot / "project.json"
    if not project_file.exists():
        return None
    try:
        payload = json.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    word_count = payload.get("word_count")
    return word_count if isinstance(word_count, dict) else None


def resolve_slot_db_path(cfg: dict[str, Any], project_root: str | Path | None = None) -> Path:
    paths = build_project_paths(project_root)
    registry = _load_registry(paths)
    active_slot = registry.get("active_slot", "")
    if active_slot:
        slot_db = paths.workspace_root / active_slot / "novel.db"
        if slot_db.exists():
            return slot_db
    return resolve_path(paths.project_root, cfg.get("db_path", "./data/novel_memory.db"))


def build_pipeline_context(
    *,
    novel_slug: str,
    novel_title: str = "",
    volume_no: int = 1,
    chapters_dir: str | Path | None = None,
    db_path: str | Path | None = None,
    project_root: str | Path | None = None,
    config_path: str | Path | None = None,
) -> PipelineContext:
    paths = build_project_paths(project_root, config_path)
    cfg = load_json_config(paths.config_path, paths.project_root)
    registry = _load_registry(paths)
    active_slot = registry.get("active_slot", "")

    if db_path:
        resolved_db_path = resolve_path(paths.project_root, db_path)
        cfg["db_path"] = str(resolved_db_path)
    else:
        resolved_db_path = resolve_slot_db_path(cfg, paths.project_root)
        cfg["db_path"] = str(resolved_db_path)

    wc_rules = cfg.get("word_count", {})
    slot_word_count = _resolve_slot_word_count(paths, active_slot)
    if slot_word_count:
        wc_rules = slot_word_count

    novels_root = resolve_path(paths.project_root, cfg.get("novels_root", "./novels"))
    exports_root = resolve_path(paths.project_root, cfg.get("exports_root", "./exports"))
    reports_root = resolve_path(paths.project_root, cfg.get("reports_root", "./exports/reports"))
    outputs_root = resolve_path(paths.project_root, cfg.get("outputs_root", "./outputs"))
    tmp_root = resolve_path(paths.project_root, cfg.get("tmp_root", "./tmp"))

    if chapters_dir:
        resolved_chapters_dir = resolve_path(paths.project_root, chapters_dir)
    elif active_slot:
        slot_dir = paths.workspace_root / active_slot
        resolved_chapters_dir = slot_dir / "chapters"
        if volume_no > 1:
            resolved_chapters_dir = resolved_chapters_dir / f"第{volume_no:02d}卷"
    else:
        resolved_chapters_dir = novels_root / novel_slug / f"第{volume_no:02d}卷"

    scene_quality = cfg.get("scene_quality", {})
    default_normal = wc_rules.get("normal", {"min": 1300, "best_min": 1900, "best_max": 2800, "max": 3300})
    final_title = novel_title or cfg.get("default_novel_title", novel_slug) or novel_slug

    return PipelineContext(
        project_root=paths.project_root,
        config_path=paths.config_path,
        cfg=cfg,
        novel_slug=novel_slug,
        novel_title=final_title,
        volume_no=volume_no,
        db_path=resolved_db_path,
        novels_root=novels_root,
        exports_root=exports_root,
        reports_root=reports_root,
        outputs_root=outputs_root,
        tmp_root=tmp_root,
        workspace_root=paths.workspace_root,
        active_slot=active_slot,
        chapters_dir=resolved_chapters_dir,
        state_dir=exports_root / "pipeline_state",
        wc_rules=wc_rules,
        wc_default=wc_rules.get("normal", default_normal),
        allow_short_chapter=bool(cfg.get("allow_short_chapter", False)),
        min_scenes=int(scene_quality.get("min_effective_scenes", 1)),
    )


def build_guard_context(
    context: PipelineContext | None,
    *,
    chapter_no: int,
    prev_brief: dict[str, Any] | None = None,
    genre: str | None = None,
    voice_context: dict[str, Any] | None = None,
    perplexity_config: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    guard_context: dict[str, Any] = {
        "chapter_no": chapter_no,
        "project_root": str(context.project_root) if context else "",
        "novel_slug": context.novel_slug if context else "",
        "genre": genre or "",
        "previous_chapter_summary": None,
        "voice_context": voice_context or {},
        "perplexity_config": perplexity_config or (context.cfg if context else {}),
        "meme_packs_dir": "",
        "dialect_packs": [],
    }
    if prev_brief:
        guard_context["previous_chapter_summary"] = {
            "ending_hook": prev_brief.get("next_chapter_hooks", ""),
            "content_preview": prev_brief.get("ending_state", "") or prev_brief.get("opening_state", ""),
        }
    if voice_context:
        packs = voice_context.get("packs", []) or []
        guard_context["meme_packs_dir"] = voice_context.get("meme_packs_dir", "")
        guard_context["dialect_packs"] = [pack for pack in packs if "dialect" in str(pack).lower()]
    if extra:
        guard_context.update(extra)
    return guard_context
