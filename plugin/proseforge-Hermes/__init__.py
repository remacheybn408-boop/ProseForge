"""
proseforge-engine plugin — Hermes 原生 ProseForge 引擎封装

将 ProseForge 的写作流水线暴露为 2 个 Hermes 工具：
  nf_pipeline — 写作流水线（pre/post/review/batch/volume）
  nf_project  — 项目管理（init/create/list/status/outline/export）
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 项目路径 ──────────────────────────────────────────────────────────
PROSEFORGE_DIR = Path(r"D:\Project\ProseForge")
PROSEFORGE_VENV_PYTHON = PROSEFORGE_DIR / ".venv" / "Scripts" / "python.exe"


def _ensure_import() -> None:
    """Ensure the project is importable, refresh src.* modules, and load pipeline entry points."""
    root = str(PROSEFORGE_DIR.resolve())
    if root not in sys.path:
        sys.path.insert(0, root)
    os.chdir(root)
    global pipeline_pre, pipeline_post, pipeline_volume, pipeline_rewrite, pipeline_accept
    stale = [k for k in list(sys.modules) if k.startswith("src.") or k == "src"]
    for k in stale:
        del sys.modules[k]
    from src.pipeline.pre import run_pre as _run_pre
    from src.pipeline.post import run_post as _run_post
    from src.pipeline.volume import volume_post as _volume_post
    from src.pipeline.rewrite import run_rewrite as _run_rewrite, run_accept as _run_accept
    pipeline_pre = _run_pre
    pipeline_post = _run_post
    pipeline_volume = _volume_post
    pipeline_rewrite = _run_rewrite
    pipeline_accept = _run_accept


# ── 公共辅助 ──────────────────────────────────────────────────────────

def _post(args: dict) -> dict:
    """post chapter 的公共流程包装"""
    _ensure_import()
    try:
        result = pipeline_post(
            novel_slug=args["slug"],
            novel_title=args["title"],
            volume_no=int(args["vol_no"]),
            chapter_no=int(args["chapter_no"]),
            chapter_type=args.get("chapter_type", "normal"),
        )
        if result is None:
            return {"status": "ok", "message": "completed (no structured result)"}
        return result
    except Exception as e:
        logger.exception("nf_pipeline post failed")
        return {"status": "error", "message": str(e)}


# ── nf_pipeline — 写作流水线 ─────────────────────────────────────────

def _review_mode(args: dict) -> str:
    mode = str(args.get("mode", "full")).strip().lower()
    if mode not in {"light", "full"}:
        raise ValueError("mode 必须是 light 或 full")
    return mode


def _review_candidate_dirs(vol_no: int, slug: str) -> list[Path]:
    from src.pipeline._base import load_config

    candidates = []
    registry_path = PROSEFORGE_DIR / "workspace" / "registry.json"
    active_slot = ""
    if registry_path.exists():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            active_slot = registry.get("active_slot", "")
        except Exception:
            active_slot = ""

    if active_slot:
        slot_chapters = PROSEFORGE_DIR / "workspace" / active_slot / "chapters"
        candidates.append(slot_chapters / f"第{vol_no:02d}卷")
        candidates.append(slot_chapters)
        if slot_chapters.exists():
            candidates.extend(sorted(path for path in slot_chapters.glob("第*卷") if path.is_dir()))

    cfg = load_config(None)
    novels_root = Path(cfg.get("novels_root", "./novels"))
    if not novels_root.is_absolute():
        novels_root = PROSEFORGE_DIR / novels_root
    candidates.append(novels_root / slug / f"第{vol_no:02d}卷")
    candidates.append(novels_root / slug)

    deduped = []
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        deduped.append(path)
    return deduped


def _load_review_content(args: dict) -> tuple[str, Path]:
    from src.pipeline._base import _find_chapter_file, _strip_selfcheck

    chapter_no = int(args["chapter_no"])
    vol_no = int(args["vol_no"])
    for directory in _review_candidate_dirs(vol_no, args["slug"]):
        chapter_file = _find_chapter_file(chapter_no, directory)
        if chapter_file is None:
            continue
        content = chapter_file.read_text(encoding="utf-8")
        return _strip_selfcheck(content).strip(), chapter_file

    raise FileNotFoundError(f"找不到第{chapter_no}章 TXT，无法执行 review")


_PIPELINE_ACTIONS = {"pre", "post", "review", "batch", "volume", "rewrite", "accept"}


def _handle_pipeline(args: dict, **kw) -> dict:
    action = args.get("action", "")
    if action not in _PIPELINE_ACTIONS:
        return {
            "status": "error",
            "message": f"action 必须是 {'/'.join(sorted(_PIPELINE_ACTIONS))}，而不是 '{action}'",
        }

    _ensure_import()

    try:
        if action == "pre":
            result = pipeline_pre(
                novel_slug=args["slug"],
                novel_title=args["title"],
                volume_no=int(args["vol_no"]),
                chapter_no=int(args["chapter_no"]),
                chapter_type=args.get("chapter_type", "normal"),
            )
            return result if result else {"status": "ok", "message": "pre completed"}

        elif action == "post":
            return _post(args)

        elif action == "review":
            from src.agents.orchestrator import run_agent_review

            mode = _review_mode(args)
            content, chapter_path = _load_review_content(args)
            result = run_agent_review(
                content,
                chapter_no=int(args["chapter_no"]),
                mode=mode,
            )
            if isinstance(result, dict):
                result.setdefault("chapter_file", str(chapter_path))
                result.setdefault("mode", mode)
                return result
            return {
                "status": "ok",
                "result": str(result),
                "chapter_file": str(chapter_path),
                "mode": mode,
            }

        elif action == "batch":
            results = []
            for ch in range(int(args["from_ch"]), int(args["to_ch"]) + 1):
                r = _post({
                    "slug": args["slug"],
                    "title": args["title"],
                    "vol_no": args["vol_no"],
                    "chapter_no": ch,
                    "chapter_type": args.get("chapter_type", "normal"),
                })
                results.append({"chapter_no": ch, "result": r})
            return {"status": "ok", "results": results}

        elif action == "volume":
            result = pipeline_volume(
                novel_slug=args["slug"],
                novel_title=args["title"],
                volume_no=int(args["vol_no"]),
            )
            return result if result else {"status": "ok", "message": "volume completed"}

        elif action == "rewrite":
            result = pipeline_rewrite(
                novel_slug=args["slug"],
                novel_title=args["title"],
                volume_no=int(args["vol_no"]),
                chapter_no=int(args["chapter_no"]),
                chapter_type=args.get("chapter_type", "normal"),
            )
            return result if result else {"status": "ok", "message": "rewrite completed"}

        elif action == "accept":
            result = pipeline_accept(
                novel_slug=args["slug"],
                novel_title=args["title"],
                volume_no=int(args["vol_no"]),
                chapter_no=int(args["chapter_no"]),
                chapter_type=args.get("chapter_type", "normal"),
                ingest=bool(args.get("ingest", False)),
            )
            return result if result else {"status": "ok", "message": "accept completed"}

    except Exception as e:
        logger.exception("nf_pipeline %s failed", action)
        return {"status": "error", "message": str(e)}


# ── nf_project — 项目管理 ────────────────────────────────────────────

_PROJECT_ACTIONS = {"init", "create", "list", "status", "outline", "export"}


def _handle_project(args: dict, **kw) -> dict:
    action = args.get("action", "")
    if action not in _PROJECT_ACTIONS:
        return {
            "status": "error",
            "message": f"action 必须是 {'/'.join(sorted(_PROJECT_ACTIONS))}，而不是 '{action}'",
        }

    _ensure_import()

    try:
        if action == "init":
            from src.db.slot_manager import SlotManager

            project_root = PROSEFORGE_DIR
            ws_dir = project_root / "workspace"
            ws_dir.mkdir(exist_ok=True)
            SlotManager(project_root).init()
            return {"status": "ok", "message": "工作区初始化完成", "workspace": str(ws_dir)}

        elif action == "create":
            from src.db.slot_manager import SlotManager

            mgr = SlotManager(PROSEFORGE_DIR)
            mgr.create(args["slot_name"], args["title"])
            return {
                "status": "ok",
                "message": f"小说 '{args['title']}' 创建完成",
                "slot": args["slot_name"],
            }

        elif action == "list":
            from src.db.registry import Registry

            reg = Registry(PROSEFORGE_DIR / "workspace")
            slots = reg.list_slots()
            return {"status": "ok", "slots": slots}

        elif action == "status":
            project_root = PROSEFORGE_DIR
            registry_path = project_root / "workspace" / "registry.json"
            if not registry_path.exists():
                return {
                    "status": "noop",
                    "message": "工作区未初始化",
                    "workspace": str(project_root / "workspace"),
                }
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            active_slot = registry.get("active_slot", "")
            slots = {}
            if active_slot:
                proj_path = project_root / "workspace" / active_slot / "project.json"
                if proj_path.exists():
                    proj = json.loads(proj_path.read_text(encoding="utf-8"))
                    slots[active_slot] = {
                        "title": proj.get("title", ""),
                        "slug": proj.get("slug", active_slot),
                    }
            return {"status": "ok", "active_slot": active_slot, "slots": slots, "registry": registry}

        elif action == "outline":
            sub_action = args.get("sub_action", "")
            if sub_action not in ("add", "list", "switch"):
                return {
                    "status": "error",
                    "message": f"outline sub_action 必须是 add/list/switch，而不是 '{sub_action}'",
                }
            from src.outline.outline_manager import OutlineManager

            manager = OutlineManager(PROSEFORGE_DIR)
            if sub_action == "add":
                file_path = args.get("file_path", "")
                if not file_path:
                    return {"status": "error", "message": "add 需要 file_path 参数"}
                p = Path(file_path)
                if not p.exists():
                    return {"status": "error", "message": f"文件不存在: {file_path}"}
                result = manager.add_outline(content=p.read_text(encoding="utf-8"), title=p.stem)
                return {"status": "ok", "result": str(result)}
            elif sub_action == "list":
                outlines = manager.list_outlines()
                return {"status": "ok", "outlines": outlines}
            elif sub_action == "switch":
                outline_id = args.get("outline_id", "")
                if not outline_id:
                    return {"status": "error", "message": "switch 需要 outline_id 参数"}
                result = manager.switch_outline(outline_id)
                return {"status": "ok", "result": str(result)}

        elif action == "export":
            from src.pipeline.export_novel import main as export_main
            import sys as _sys

            cli_args = []
            slug = args.get("slug", "")
            fmt = args.get("format", "txt")
            output = args.get("output", "")
            if slug:
                cli_args.extend(["--slug", slug])
            if fmt:
                cli_args.extend(["--format", fmt])
            if output:
                cli_args.extend(["--output", output])
            _sys.argv = ["export"] + cli_args
            result = export_main()
            return {"status": "ok" if result == 0 else "error", "exit_code": result}

    except Exception as e:
        logger.exception("nf_project %s failed", action)
        return {"status": "error", "message": str(e)}


# ── Schema 定义 ─────────────────────────────────────────────────────────



NF_PIPELINE_SCHEMA = {
    "name": "nf_pipeline",
    "description": "Writing pipeline. action=pre/post/review(agent review)/batch(from_ch~to_ch)/volume/rewrite(产改写卡)/accept(diff+可选入库)",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["pre", "post", "review", "batch", "volume", "rewrite", "accept"],
                "description": "Pipeline action. Required.",
            },
            "slug": {
                "type": "string",
                "description": "Novel slug. Required by pre/post/review/batch/volume.",
            },
            "title": {
                "type": "string",
                "description": "Novel title. Required by pre/post/review/batch/volume.",
            },
            "vol_no": {
                "type": "integer",
                "description": "Volume number. Required by pre/post/review/batch/volume.",
            },
            "chapter_no": {
                "type": "integer",
                "description": "Chapter number. Required by pre/post/review/rewrite/accept.",
            },
            "ingest": {
                "type": "boolean",
                "description": "accept: 通过审核后入库（追加版本快照，不覆盖原稿），默认 false。",
            },
            "chapter_type": {
                "type": "string",
                "enum": ["normal", "key", "climax"],
                "description": "Chapter type. Used by pre/post/batch, defaults to normal.",
            },
            "mode": {
                "type": "string",
                "enum": ["light", "full"],
                "description": "Review mode. Used by review, defaults to full.",
            },
            "from_ch": {
                "type": "integer",
                "description": "Batch start chapter number.",
            },
            "to_ch": {
                "type": "integer",
                "description": "Batch end chapter number.",
            },
        },
        "required": ["action"],
    },
}


NF_PROJECT_SCHEMA = {
    "name": "nf_project",
    "description": "项目管理。action=init(初始化工作区)/create(创建小说槽位)/list(槽位列表)/status(工作区状态)/outline(大纲管理 add/list/switch)/export(导出小说)",
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["init", "create", "list", "status", "outline", "export"],
                "description": "项目操作。必填。",
            },
            "slot_name": {
                "type": "string",
                "description": "槽位标识（英文，如 'gwdz'）。create 必填。",
            },
            "title": {
                "type": "string",
                "description": "小说中文名。create 必填。",
            },
            "slug": {
                "type": "string",
                "description": "小说 slug。export 使用（默认当前激活槽位）。",
            },
            "format": {
                "type": "string",
                "enum": ["txt", "md"],
                "description": "导出格式。export 使用，默认 txt。",
            },
            "output": {
                "type": "string",
                "description": "输出路径。export 使用（默认自动生成）。",
            },
            "sub_action": {
                "type": "string",
                "enum": ["add", "list", "switch"],
                "description": "outline 子操作。outline 必填。",
            },
            "file_path": {
                "type": "string",
                "description": "大纲 JSON 文件路径。outline add 必填。",
            },
            "outline_id": {
                "type": "string",
                "description": "大纲 ID。outline switch 必填。",
            },
        },
        "required": ["action"],
    },
}


# ── 注册入口 ────────────────────────────────────────────────────────────

def register(ctx) -> None:
    """Registered by Hermes plugin loader on enable."""
    if not PROSEFORGE_DIR.exists():
        logger.warning("proseforge-engine: project dir %s not found — not registering.", PROSEFORGE_DIR)
        return

    ctx.register_tool(
        name="nf_pipeline",
        toolset="proseforge-engine",
        schema=NF_PIPELINE_SCHEMA,
        handler=_handle_pipeline,
        emoji="\N{WRENCH}",
    )
    ctx.register_tool(
        name="nf_project",
        toolset="proseforge-engine",
        schema=NF_PROJECT_SCHEMA,
        handler=_handle_project,
        emoji="\N{OPEN FILE FOLDER}",
    )

    logger.info("proseforge-engine: registered 2 tools (nf_pipeline, nf_project) from %s", PROSEFORGE_DIR)
