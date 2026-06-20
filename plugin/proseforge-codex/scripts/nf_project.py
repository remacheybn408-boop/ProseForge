#!/usr/bin/env python3
"""Local CLI wrapper for Novel Forge project-management workflows."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def _ensure_repo_import() -> None:
    root = str(REPO_ROOT)
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


def _project_status() -> dict:
    registry_path = REPO_ROOT / "workspace" / "registry.json"
    if not registry_path.exists():
        return {
            "status": "noop",
            "message": "workspace is not initialized",
            "workspace": str(REPO_ROOT / "workspace"),
        }

    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    active_slot = registry.get("active_slot", "")
    slots: dict[str, dict] = {}
    if active_slot:
        project_path = REPO_ROOT / "workspace" / active_slot / "project.json"
        if project_path.exists():
            project = json.loads(project_path.read_text(encoding="utf-8"))
            slots[active_slot] = {
                "title": project.get("title", ""),
                "slug": project.get("slug", active_slot),
            }

    return {"status": "ok", "active_slot": active_slot, "slots": slots, "registry": registry}


def _run_project(args: argparse.Namespace) -> object:
    _ensure_repo_import()

    if args.action == "init":
        from src.db.slot_manager import SlotManager

        manager = SlotManager(REPO_ROOT)
        result = manager.init_workspace()
        result["workspace"] = str(REPO_ROOT / "workspace")
        return result

    if args.action == "create":
        _require_args(args, ["slot_name", "title"])
        from src.db.slot_manager import SlotManager

        manager = SlotManager(REPO_ROOT)
        result = manager.create_slot(args.slot_name, ensure_registry=True, name=args.title, description=args.title)
        return {
            "status": "ok",
            "message": f"slot '{args.slot_name}' created",
            "slot": args.slot_name,
            "result": result,
        }

    if args.action == "list":
        from src.db.registry import Registry

        registry = Registry(REPO_ROOT)
        return {"status": "ok", "slots": registry.list_slots()}

    if args.action == "status":
        return _project_status()

    if args.action == "outline":
        _require_args(args, ["sub_action"])
        from src.outline.outline_manager import OutlineManager

        manager = OutlineManager(REPO_ROOT)
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
