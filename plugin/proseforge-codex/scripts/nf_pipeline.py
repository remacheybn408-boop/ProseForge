#!/usr/bin/env python3
"""Local CLI wrapper for ProseForge pipeline workflows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


PROJECT_ROOT_ENV = "PROSEFORGE_PROJECT_ROOT"


def _looks_like_project_root(path: Path) -> bool:
    return (
        (path / "src").is_dir()
        and (path / "database" / "schema.sql").is_file()
        and (path / "pyproject.toml").is_file()
    )


def _argv_project_root(argv: list[str]) -> str | None:
    for index, arg in enumerate(argv):
        if arg == "--project-root" and index + 1 < len(argv):
            return argv[index + 1]
        if arg.startswith("--project-root="):
            return arg.split("=", 1)[1]
    return None


def _candidate_roots() -> list[Path]:
    starts = [Path.cwd(), Path(__file__).resolve().parent]
    candidates: list[Path] = []
    seen: set[Path] = set()
    for start in starts:
        for path in (start, *start.parents):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                candidates.append(resolved)
    return candidates


def _discover_project_root() -> Path:
    explicit = _argv_project_root(sys.argv[1:]) or os.environ.get(PROJECT_ROOT_ENV)
    if explicit:
        root = Path(explicit).expanduser().resolve()
        if _looks_like_project_root(root):
            return root
        raise RuntimeError(f"--project-root does not look like a ProseForge repo: {root}")

    for root in _candidate_roots():
        if _looks_like_project_root(root):
            return root

    raise RuntimeError(
        "cannot locate ProseForge project root; run from the repo root, "
        f"pass --project-root, or set {PROJECT_ROOT_ENV}"
    )


DEFAULT_PROJECT_ROOT = _discover_project_root()
if str(DEFAULT_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(DEFAULT_PROJECT_ROOT))

from src.agents.orchestrator import run_agent_review
from src.pipeline._base import _find_chapter_file, _strip_selfcheck
from src.pipeline.post import run_post
from src.pipeline.pre import run_pre
from src.pipeline.rewrite import run_accept, run_rewrite
from src.pipeline.volume import volume_post
from src.utils.config_utils import load_json_config, resolve_path
SUPPORTED_ACTIONS = ["pre", "post", "review", "batch", "volume", "rewrite", "accept"]


def _require_args(args: argparse.Namespace, fields: list[str]) -> None:
    missing = [field for field in fields if getattr(args, field) in (None, "")]
    if missing:
        joined = ", ".join(f"--{field.replace('_', '-')}" for field in missing)
        raise ValueError(f"missing required arguments for action '{args.action}': {joined}")


def _project_root(args: argparse.Namespace) -> Path:
    return Path(args.project_root).expanduser().resolve() if args.project_root else DEFAULT_PROJECT_ROOT


def _review_candidate_dirs(project_root: Path, vol_no: int, slug: str, config_path: str | None) -> list[Path]:
    cfg = load_json_config(config_path, project_root)
    candidates: list[Path] = []
    registry_path = project_root / "workspace" / "registry.json"
    active_slot = ""
    if registry_path.exists():
        try:
            active_slot = json.loads(registry_path.read_text(encoding="utf-8")).get("active_slot", "")
        except Exception:
            active_slot = ""

    if active_slot:
        slot_chapters = project_root / "workspace" / active_slot / "chapters"
        candidates.append(slot_chapters / f"第{vol_no:02d}卷")
        candidates.append(slot_chapters)

    novels_root = resolve_path(project_root, cfg.get("novels_root", "./novels"))
    candidates.append(novels_root / slug / f"第{vol_no:02d}卷")
    candidates.append(novels_root / slug)

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


def _load_review_content(project_root: Path, slug: str, vol_no: int, chapter_no: int, config_path: str | None):
    for directory in _review_candidate_dirs(project_root, vol_no, slug, config_path):
        chapter_file = _find_chapter_file(chapter_no, directory)
        if chapter_file is None:
            continue
        return _strip_selfcheck(chapter_file.read_text(encoding="utf-8")).strip(), chapter_file
    raise FileNotFoundError(f"cannot find chapter text for chapter {chapter_no}")


def _run_pipeline(args: argparse.Namespace) -> object:
    project_root = _project_root(args)
    shared = {
        "project_root": project_root,
        "config_path": args.config_path,
    }

    if args.action == "pre":
        _require_args(args, ["slug", "title", "vol_no", "chapter_no"])
        return run_pre(
            novel_slug=args.slug,
            novel_title=args.title,
            volume_no=args.vol_no,
            chapter_no=args.chapter_no,
            chapter_type=args.chapter_type,
            **shared,
        )

    if args.action == "post":
        _require_args(args, ["slug", "title", "vol_no", "chapter_no"])
        return run_post(
            novel_slug=args.slug,
            novel_title=args.title,
            volume_no=args.vol_no,
            chapter_no=args.chapter_no,
            chapter_type=args.chapter_type,
            **shared,
        )

    if args.action == "review":
        _require_args(args, ["slug", "vol_no", "chapter_no"])
        content, chapter_path = _load_review_content(
            project_root,
            args.slug,
            args.vol_no,
            args.chapter_no,
            args.config_path,
        )
        result = run_agent_review(content, chapter_no=args.chapter_no, mode=args.mode)
        if isinstance(result, dict):
            result.setdefault("chapter_file", str(chapter_path))
            result.setdefault("mode", args.mode)
            return result
        return {"status": "ok", "result": str(result), "chapter_file": str(chapter_path), "mode": args.mode}

    if args.action == "batch":
        _require_args(args, ["slug", "title", "vol_no", "from_ch", "to_ch"])
        results = []
        for chapter_no in range(args.from_ch, args.to_ch + 1):
            result = run_post(
                novel_slug=args.slug,
                novel_title=args.title,
                volume_no=args.vol_no,
                chapter_no=chapter_no,
                chapter_type=args.chapter_type,
                **shared,
            )
            results.append({"chapter_no": chapter_no, "result": result})
        return {"status": "ok", "results": results}

    if args.action == "volume":
        _require_args(args, ["slug", "title", "vol_no"])
        return volume_post(
            novel_slug=args.slug,
            novel_title=args.title,
            volume_no=args.vol_no,
            **shared,
        )

    if args.action == "rewrite":
        _require_args(args, ["slug", "title", "vol_no", "chapter_no"])
        return run_rewrite(
            novel_slug=args.slug,
            novel_title=args.title,
            volume_no=args.vol_no,
            chapter_no=args.chapter_no,
            chapter_type=args.chapter_type,
            **shared,
        )

    if args.action == "accept":
        _require_args(args, ["slug", "title", "vol_no", "chapter_no"])
        return run_accept(
            novel_slug=args.slug,
            novel_title=args.title,
            volume_no=args.vol_no,
            chapter_no=args.chapter_no,
            chapter_type=args.chapter_type,
            ingest=args.ingest,
            **shared,
        )

    raise ValueError(f"unsupported action: {args.action}")


def _exit_code(payload: object) -> int:
    if isinstance(payload, dict):
        return 1 if payload.get("status") == "error" else 0
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict) and item.get("status") == "error":
                return 1
            result = item.get("result") if isinstance(item, dict) else None
            if isinstance(result, dict) and result.get("status") == "error":
                return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ProseForge pipeline wrapper")
    parser.add_argument("--action", required=True, choices=SUPPORTED_ACTIONS)
    parser.add_argument("--slug")
    parser.add_argument("--title")
    parser.add_argument("--vol-no", dest="vol_no", type=int)
    parser.add_argument("--chapter-no", dest="chapter_no", type=int)
    parser.add_argument("--chapter-type", dest="chapter_type", default="normal", choices=["normal", "key", "climax"])
    parser.add_argument("--mode", default="full", choices=["light", "full"])
    parser.add_argument("--from-ch", dest="from_ch", type=int)
    parser.add_argument("--to-ch", dest="to_ch", type=int)
    parser.add_argument("--ingest", action="store_true", help="accept: 通过审核后入库（追加版本快照，不覆盖）")
    parser.add_argument("--project-root")
    parser.add_argument("--config-path")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        result = _run_pipeline(args)
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return _exit_code(result)


if __name__ == "__main__":
    raise SystemExit(main())
