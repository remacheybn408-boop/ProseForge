"""User-facing ProseForge CLI.

This module owns command syntax and JSON output; domain operations remain in
the existing services and repositories.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import sqlite3
import sys
from pathlib import Path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proseforge")
    parser.add_argument("--project-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor")

    project = sub.add_parser("project")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_sub.add_parser("init")
    project_sub.add_parser("list")
    project_sub.add_parser("status")
    create = project_sub.add_parser("create")
    create.add_argument("--slug", required=True)
    create.add_argument("--title", required=True)

    chapter = sub.add_parser("chapter")
    chapter_sub = chapter.add_subparsers(dest="chapter_command", required=True)
    for name in ("pre", "post"):
        command = chapter_sub.add_parser(name)
        command.add_argument("chapter_no", type=int)
        command.add_argument("--slug")
        command.add_argument("--title", default="")
        command.add_argument("--volume", type=int, default=1)
        command.add_argument("--type", dest="chapter_type", default="normal")
        command.add_argument("--slot", dest="slot_id")
    return parser


def _json_print(payload: dict) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _doctor(root: Path) -> dict:
    schema = root / "database" / "schema.sql"
    workspace = root / "workspace"
    project_check = {"ok": False, "status": "unavailable"}
    database_check = {"ok": False, "status": "unavailable"}
    try:
        from src.db.registry import Registry
        registry = Registry(root)
        active_slot = registry.get_active_slot()
        if active_slot:
            project_file = workspace / active_slot / "project.json"
            project_check = {
                "ok": project_file.is_file(),
                "status": "ready" if project_file.is_file() else "missing",
                "slot": active_slot,
                "path": str(project_file),
            }
            db_file = workspace / active_slot / "novel.db"
            if db_file.is_file():
                try:
                    with sqlite3.connect(str(db_file)) as conn:
                        conn.execute("PRAGMA user_version").fetchone()
                        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone()
                    database_check = {"ok": True, "status": "ready", "path": str(db_file)}
                except sqlite3.Error as exc:
                    database_check = {"ok": False, "status": "unhealthy", "path": str(db_file), "error": str(exc)}
            else:
                database_check = {"ok": False, "status": "missing", "path": str(db_file)}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        project_check = {"ok": False, "status": "invalid", "error": str(exc)}
    rag = {"ok": False, "status": "unavailable"}
    try:
        import chromadb  # noqa: F401
        import sentence_transformers  # noqa: F401
        rag = {"ok": True, "status": "available"}
    except Exception as exc:
        rag = {"ok": False, "status": "unavailable", "error": str(exc)}
    return {
        "status": "ok",
        "project_root": str(root),
        "checks": {
            "schema": {"ok": schema.is_file(), "path": str(schema)},
            "workspace": {"ok": workspace.is_dir(), "path": str(workspace)},
            "project": project_check,
            "database": database_check,
            "rag": rag,
        },
    }


def _project(root: Path, args: argparse.Namespace) -> dict:
    from src.db.registry import Registry
    from src.db.slot_manager import SlotManager

    manager = SlotManager(root)
    if args.project_command == "init":
        result = manager.init_workspace()
        result["workspace"] = str(root / "workspace")
        return result
    if args.project_command == "list":
        return {"status": "ok", "slots": Registry(root).list_slots()}
    if args.project_command == "status":
        registry = Registry(root)
        return {"status": "ok", "active_slot": registry.get_active_slot(), "slots": registry.list_slots()}
    result = manager.create_slot(
        args.slug, name=args.title, description=args.title, slug=args.slug
    )
    manager.registry.set_active_slot(args.slug)
    return {"status": "ok", "active_slot": args.slug, "result": result}


def _active_project(root: Path, slot_id: str | None = None) -> tuple[str, str, str]:
    registry = json.loads((root / "workspace" / "registry.json").read_text(encoding="utf-8"))
    slot = slot_id or registry.get("active_slot")
    if not slot:
        raise ValueError("no active project; run 'proseforge project create' first")
    project_file = root / "workspace" / slot / "project.json"
    project = json.loads(project_file.read_text(encoding="utf-8"))
    return project.get("slug", slot), project.get("title", slot), slot


def _chapter(root: Path, args: argparse.Namespace) -> dict:
    slug, active_title, slot_id = _active_project(root, args.slot_id)
    slug = args.slug or slug
    title = args.title or active_title
    if args.chapter_command == "pre":
        from src.application.pipeline_service import PipelineService, PreChapterRequest
        result = PipelineService().pre(PreChapterRequest(
            project_root=root, slot_id=slot_id, chapter_no=args.chapter_no,
            chapter_type=args.chapter_type, novel_slug=slug,
            novel_title=title, volume_no=args.volume,
        ))
    else:
        from src.application.pipeline_service import PipelineService, PostChapterRequest
        result = PipelineService().post(PostChapterRequest(
            project_root=root, slot_id=slot_id, chapter_no=args.chapter_no,
            chapter_type=args.chapter_type, novel_slug=slug,
            novel_title=title, volume_no=args.volume,
        ))
    return {"status": "ok", "operation": f"chapter.{args.chapter_command}", "result": result}


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(args.project_root).expanduser().resolve()
    try:
        noise = io.StringIO()
        with contextlib.redirect_stdout(noise):
            if args.command == "doctor":
                payload = _doctor(root)
            elif args.command == "project":
                payload = _project(root, args)
            else:
                payload = _chapter(root, args)
        _json_print(payload)
        return 0
    except Exception as exc:
        _json_print({"status": "error", "error": str(exc)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
