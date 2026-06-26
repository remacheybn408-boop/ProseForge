#!/usr/bin/env python3
"""Shared config helpers for ProseForge."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

DEFAULT_DB_PATH = "./data/novel_memory.db"
DEFAULT_NOVELS_ROOT = "./novels"
DEFAULT_EXPORTS_ROOT = "./exports"
DEFAULT_REPORTS_ROOT = "./exports/reports"
DEFAULT_OUTPUTS_ROOT = "./outputs"
DEFAULT_TMP_ROOT = "./tmp"


def _deepcopy_dict(d: dict) -> dict:
    return deepcopy(d) if isinstance(d, dict) else {}


def find_project_root(start: str | Path | None = None) -> Path:
    """Best-effort repo-root discovery from a cwd, file, or directory."""
    current = Path(start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / "src").exists() and (candidate / "config.example.json").exists():
            return candidate
    return current


def normalize_config(raw: dict | None) -> dict:
    """Normalize config into the legacy runtime shape."""
    cfg = _deepcopy_dict(raw or {})
    paths = cfg.get("paths") if isinstance(cfg.get("paths"), dict) else {}
    novel = cfg.get("novel") if isinstance(cfg.get("novel"), dict) else {}

    cfg.setdefault("db_path", paths.get("db_path", DEFAULT_DB_PATH))
    cfg.setdefault("novels_root", paths.get("novels_root", DEFAULT_NOVELS_ROOT))
    cfg.setdefault("exports_root", paths.get("exports_root", DEFAULT_EXPORTS_ROOT))
    cfg.setdefault("reports_root", paths.get("reports_root", DEFAULT_REPORTS_ROOT))
    cfg.setdefault("outputs_root", paths.get("outputs_root", DEFAULT_OUTPUTS_ROOT))
    cfg.setdefault("tmp_root", paths.get("tmp_root", DEFAULT_TMP_ROOT))

    cfg.setdefault("allow_short_chapter", False)
    cfg.setdefault("default_novel_slug", novel.get("default_slug", "demo_novel"))
    cfg.setdefault("default_novel_title", novel.get("default_title", "Demo Novel"))
    cfg.setdefault("default_genre", cfg.get("default_genre", "xianxia"))
    cfg.setdefault("default_style", cfg.get("default_style", "webnovel"))

    wc = cfg.get("word_count") if isinstance(cfg.get("word_count"), dict) else {}
    normal = wc.get("normal") if isinstance(wc.get("normal"), dict) else {}
    authorized_short = wc.get("authorized_short") if isinstance(wc.get("authorized_short"), dict) else {}
    min_normal = normal.get("min", 1300)
    target_normal = normal.get("best_min", 1900)
    long_normal = normal.get("max", 3300)
    min_short = authorized_short.get("min", 300)

    default_wc = {
        "normal": {"min": min_normal, "best_min": target_normal, "best_max": 2800, "max": long_normal},
        "relationship": {"min": min_normal, "best_min": target_normal, "best_max": 2800, "max": long_normal},
        "investigation": {"min": min_normal, "best_min": target_normal, "best_max": 2800, "max": long_normal},
        "experiment": {"min": min_normal, "best_min": target_normal, "best_max": 3200, "max": 4200},
        "conflict": {"min": min_normal, "best_min": target_normal, "best_max": 3300, "max": 4200},
        "key": {"min": min_normal, "best_min": target_normal, "best_max": 3300, "max": 4200},
        "climax": {"min": min_normal, "best_min": 2300, "best_max": 3800, "max": 5500},
        "volume_finale": {"min": min_normal, "best_min": 2300, "best_max": 4200, "max": 5500},
        "authorized_short": {"min": min_short, "best_min": 500, "best_max": 900, "max": 1000},
        "fragment": {"min": min_short, "best_min": 500, "best_max": 900, "max": 1000},
    }
    merged_wc = {**default_wc, **wc}
    merged_wc["normal"] = {
        **default_wc["normal"],
        **normal,
        "min": min_normal,
        "best_min": target_normal,
        "max": long_normal,
    }
    cfg["word_count"] = merged_wc

    scene_quality = cfg.get("scene_quality") if isinstance(cfg.get("scene_quality"), dict) else {}
    cfg["scene_quality"] = {"min_effective_scenes": scene_quality.get("min_effective_scenes", 1)}

    # 兜底其它常用 config 字段，避免下游 cfg.get("xxx").get(...) 在缺字段时 None→AttributeError
    cfg.setdefault("orchestrator_mode", "standard")
    cfg.setdefault("quality_policy", {})
    if isinstance(cfg["quality_policy"], dict):
        cfg["quality_policy"].setdefault("max_final_revision_tasks", 5)
        cfg["quality_policy"].setdefault("min_warning_confidence", 0.55)
        cfg["quality_policy"].setdefault("deduplicate_warnings", True)
        cfg["quality_policy"].setdefault("pace_level", "normal")
    else:
        cfg["quality_policy"] = {
            "max_final_revision_tasks": 5,
            "min_warning_confidence": 0.55,
            "deduplicate_warnings": True,
            "pace_level": "normal",
        }
    cfg.setdefault("agents", {})
    if not isinstance(cfg["agents"], dict):
        cfg["agents"] = {}

    return cfg


def resolve_path(project_root: str | Path, value: str | Path) -> Path:
    """Resolve a config path relative to project root."""
    path = Path(value)
    if not path.is_absolute():
        path = Path(project_root) / path
    return path


def load_default_config(project_root: str | Path | None = None) -> dict:
    """Load defaults from config.example.json, falling back to normalized built-ins."""
    root = find_project_root(project_root)
    example = root / "config.example.json"
    if example.exists():
        return normalize_config(json.loads(example.read_text(encoding="utf-8")))
    return normalize_config({})


def load_json_config(config_path: str | Path | None, project_root: str | Path | None = None) -> dict:
    """Load and normalize config; fall back to config.json then config.example.json."""
    root = find_project_root(project_root)
    candidates: list[Path] = []
    if config_path:
        path = Path(config_path)
        if not path.is_absolute():
            path = root / path
        candidates.append(path)
    candidates.extend([root / "config.json", root / "config.example.json"])
    for path in candidates:
        if path.exists():
            return normalize_config(json.loads(path.read_text(encoding="utf-8")))
    return load_default_config(root)
