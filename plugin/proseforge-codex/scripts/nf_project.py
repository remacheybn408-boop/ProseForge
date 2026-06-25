#!/usr/bin/env python3
"""Local CLI wrapper for Novel Forge project-management workflows."""

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


def _discover_project_root(explicit: str | None = None) -> Path:
    explicit = explicit or os.environ.get(PROJECT_ROOT_ENV)
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


def _ensure_repo_import(project_root: Path) -> None:
    root = str(project_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)
    stale = [name for name in list(sys.modules) if name == "src" or name.startswith("src.")]
    for name in stale:
        del sys.modules[name]


def _require_args(args: argparse.Namespace, fields: list[str]) -> None:
    missing = [field for field in fields if getattr(args, field) in (None, "")]
    if missing:
        joined = ", ".join(f"--{field.replace('_', '-')}" for field in missing)
        raise ValueError(f"missing required arguments for action '{args.action}': {joined}")


def _project_root(args: argparse.Namespace) -> Path:
    return _discover_project_root(args.project_root)


def _project_status(project_root: Path) -> dict:
    registry_path = project_root / "workspace" / "registry.json"
    if not registry_path.exists():
        return {
            "status": "noop",
            "message": "workspace is not initialized",
            "workspace": str(project_root / "workspace"),
        }

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    active_slot = registry.get("active_slot", "")
    slots: dict[str, dict] = {}
    if active_slot:
        project_path = project_root / "workspace" / active_slot / "project.json"
        if project_path.exists():
            project = json.loads(project_path.read_text(encoding="utf-8"))
            slots[active_slot] = {
                "title": project.get("title", ""),
                "slug": project.get("slug", active_slot),
            }

    return {"status": "ok", "active_slot": active_slot, "slots": slots, "registry": registry}


def _run_project(args: argparse.Namespace) -> object:
    project_root = _project_root(args)
    _ensure_repo_import(project_root)

    if args.action == "init":
        from src.db.slot_manager import SlotManager

        manager = SlotManager(project_root)
        result = manager.init_workspace()
        result["workspace"] = str(project_root / "workspace")
        return result

    if args.action == "create":
        # 优先使用 --slug；--slot-name 保留为兼容别名
        slot_id = args.slug or args.slot_name
        if not slot_id:
            raise ValueError("missing required argument for action 'create': --slug (或兼容别名 --slot-name)")
        _require_args(args, ["title"])
        from src.db.slot_manager import SlotManager

        manager = SlotManager(project_root)
        result = manager.create_slot(slot_id, ensure_registry=True, name=args.title, description=args.title)
        return {
            "status": "ok",
            "message": f"slot '{slot_id}' created",
            "slot": slot_id,
            "result": result,
        }

    if args.action == "list":
        from src.db.registry import Registry

        registry = Registry(project_root)
        return {"status": "ok", "slots": registry.list_slots()}

    if args.action == "status":
        return _project_status(project_root)

    if args.action == "outline":
        _require_args(args, ["sub_action"])
        from src.outline.outline_manager import OutlineManager

        manager = OutlineManager(project_root)
        if args.sub_action == "add":
            _require_args(args, ["file_path"])
            file_path = Path(args.file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"outline file not found: {file_path}")
            return manager.add_outline(content=file_path.read_text(encoding="utf-8"), title=file_path.stem)
        if args.sub_action == "list":
            return {"status": "ok", "outlines": manager.list_outlines()}
        if args.sub_action == "switch":
            _require_args(args, ["outline_id"])
            return manager.switch_outline(args.outline_id)
        raise ValueError(f"unsupported outline sub-action: {args.sub_action}")

    if args.action == "export":
        from src.pipeline.export_novel import main as export_main

        cli_args: list[str] = []
        if args.slug:
            cli_args.extend(["--slug", args.slug])
        if args.format:
            cli_args.extend(["--format", args.format])
        if args.output:
            cli_args.extend(["--output", args.output])

        original_argv = sys.argv[:]
        try:
            sys.argv = ["export"] + cli_args
            exit_code = export_main()
        finally:
            sys.argv = original_argv
        return {"status": "ok" if exit_code == 0 else "error", "exit_code": exit_code}

    raise ValueError(f"unsupported action: {args.action}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Novel Forge project wrapper")
    parser.add_argument("--action", required=True, choices=["init", "create", "list", "status", "outline", "export"])
    parser.add_argument("--slot-name", dest="slot_name")
    parser.add_argument("--title")
    parser.add_argument("--slug")
    parser.add_argument("--format", choices=["txt", "md"], default="txt")
    parser.add_argument("--output")
    parser.add_argument("--sub-action", dest="sub_action", choices=["add", "list", "switch"])
    parser.add_argument("--file-path", dest="file_path")
    parser.add_argument("--outline-id", dest="outline_id")
    parser.add_argument("--project-root")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        result = _run_project(args)
    except Exception as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    if isinstance(result, dict) and result.get("status") == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
