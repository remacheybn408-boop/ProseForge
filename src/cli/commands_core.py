#!/usr/bin/env python3
"""src/cli/commands_core.py — Core CLI commands (report/guards/check/wc/init/genre/style) v0.7.0"""

from src.cli.shared import (PROJECT_ROOT, SCRIPTS_DIR, _load_project_config,
    _get_default_slug, _get_novels_root, _get_outline_dir, _resolve_post_context,
    find_chapter_file,
    _resolve_chapter_path, _story_exists, _story_missing_msg, _get_workspace_dir,
    _get_active_db_path, _get_outline_manager, _check_outline_gate, _get_story_dir)
import sys
import json
from pathlib import Path
from datetime import datetime
from version import get_version
from scripts.config_utils import normalize_config, load_json_config, resolve_path


def cmd_report():
    """Show most recent guard reports and exports."""
    print("=" * 60)
    v = get_version()
    print(f"  Novel Forge - 小说引擎 {v}")
    print("  Reports")
    print("=" * 60)
    print()

    cfg_data = _load_project_config()
    reports_dir = resolve_path(PROJECT_ROOT, cfg_data.get("reports_root", "./exports/reports"))
    if not reports_dir.exists():
        print("  No reports directory found.")
        print(f"  Expected: {reports_dir}")
        return 0

    all_reports = sorted(reports_dir.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)

    if not all_reports:
        print("  No report files found.")
        return 0

    print(f"  Found {len(all_reports)} report files in {reports_dir}")
    print()

    for rp in all_reports[:10]:
        mtime = datetime.fromtimestamp(rp.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        size = rp.stat().st_size
        size_str = f"{size:,}B" if size < 1024 else f"{size/1024:.1f}KB"
        status = "?"
        try:
            data = json.loads(rp.read_text(encoding="utf-8"))
            status = data.get("status", data.get("overall_status", "?"))
        except Exception:
            pass
        rel_path = rp.relative_to(reports_dir)
        print(f"  [{status:5s}] {mtime}  {size_str:>8s}  {rel_path}")

    if len(all_reports) > 10:
        print(f"\n  ... and {len(all_reports) - 10} more reports.")

    print()
    return 0


def cmd_guards():
    """List registered guards and their status."""
    print("=" * 60)
    v = get_version()
    print(f"  Novel Forge - 小说引擎 {v}")
    print("  Guard Registry")
    print("=" * 60)
    print()

    # Core guards from registry
    print("  [Core Guards — src/guards/]")
    try:
        from scripts.guard_registry import GUARD_RUNNERS, GUARD_LEVELS, MODE_GUARDS
        for name in sorted(GUARD_RUNNERS):
            level = GUARD_LEVELS.get(name, "?")
            print(f"    L{level} {name}")
    except ImportError:
        print("    (guard_registry not importable)")

    print()
    print("  [Guard Modes]")
    try:
        from scripts.guard_registry import MODE_GUARDS
        for mode, guards in MODE_GUARDS.items():
            print(f"    {mode}: {len(guards)} guards")
    except ImportError:
        pass

    print()
    return 0


def cmd_check(file_path: str):
    """Run the standard guard set on a chapter file (single-entry via guard_registry)."""
    fp = Path(file_path)
    if not fp.exists():
        print(f"[ERROR] File not found: {fp}")
        return 1

    content = fp.read_text(encoding="utf-8")
    print("=" * 60)
    print(f"  Checking: {fp.name}")
    print("=" * 60)

    try:
        from scripts.guard_registry import run_standard_guards
        summary = run_standard_guards(content, chapter_no=1, mode="standard")
        print(f"  Executed: {len(summary.executed_guards)} guards")
        print(f"  Skipped:  {len(summary.skipped_guards)} guards")
        print(f"  Failures: {summary.fail_count}")
        print(f"  Warnings: {summary.warn_count}")
        if summary.blocked_by:
            print(f"  BLOCKED by: {summary.blocked_by}")
        if summary.fail_count > 0:
            print(f"\n  Guard failures:")
            for r in summary.results:
                if r.status == "FAIL":
                    print(f"    [{r.guard}] {len(r.findings)} findings")
        print(f"\n  Overall: {summary.overall_status}")
    except ImportError as e:
        print(f"  [WARN] guard_registry not available: {e}")
        print(f"  Hint: run 'python novel.py post <N>' for full post-write pipeline")
    except Exception as e:
        print(f"  [WARN] guard check error: {e}")

    print("=" * 60)
    return 0


def cmd_wc(file_path: str = None):
    """Count Chinese characters in a chapter file.

    Supports both file paths and chapter numbers:
      python novel.py wc 1              # resolves to 第01卷/第1章*.txt
      python novel.py wc chapter.txt    # existing behavior
    """
    if not file_path:
        print("Usage: python novel.py wc <chapter_file.txt|chapter_number>")
        return 1

    fp = None
    # If arg is all digits, resolve to chapter file path
    if file_path.isdigit():
        chapter_no = int(file_path)
        try:
            cfg_data = _load_project_config()
            slug = _get_default_slug()
            novels_root = resolve_path(PROJECT_ROOT, cfg_data.get("novels_root", "./novels"))
            ch_dir = Path(_resolve_chapter_path(slug))
            fp = find_chapter_file(chapter_no, ch_dir)
            if not fp:
                print(f"[ERROR] Chapter {chapter_no} not found in {ch_dir}")
                return 1
        except Exception as e:
            print(f"[ERROR] Could not resolve chapter {file_path}: {e}")
            return 1
    else:
        fp = Path(file_path)

    if not fp.exists():
        print(f"[ERROR] File not found: {fp}")
        return 1
    text = fp.read_text(encoding="utf-8")
    # Count Chinese chars only (U+4E00-U+9FFF plus common CJK extensions)
    cn = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
    total = len(text)
    print(f"  {fp.name}")
    print(f"  汉字: {cn}  |  总字符: {total}  |  占比: {cn*100//total if total else 0}%")
    # Read word_count thresholds from config
    wc_min = 1300; wc_best_min = 1900; wc_max = 3300  # defaults
    try:
        cfg_path = PROJECT_ROOT / "config.json"
        if cfg_path.exists():
            cfg_data = _load_project_config()
            wc_cfg = cfg_data.get("word_count", {})
            normal = wc_cfg.get("normal", {})
            wc_min = normal.get("min", wc_min)
            wc_best_min = normal.get("best_min", wc_best_min)
            wc_max = normal.get("max", wc_max)
    except Exception:
        pass
    # Quick check against limits
    if cn < wc_min:
        print(f"  ⚠️  低于最低线 ({wc_min})，需补 {wc_min-cn} 字+")
    elif cn < wc_best_min:
        print(f"  ✅ 通过最低线，距最佳范围还差 {wc_best_min-cn} 字")
    elif cn <= wc_max:
        print(f"  ✅ 在正常范围内")
    else:
        print(f"  ⚠️  超过上限 ({wc_max})")
    return 0


def cmd_init():
    """Initialize project: create directories, copy config, init DB."""
    print("=" * 60)
    v = get_version()
    print(f"  Novel Forge - 小说引擎 {v}")
    print("  Initialize Project")
    print("=" * 60)
    print()

    cfg_path = PROJECT_ROOT / "config.json"
    if not cfg_path.exists():
        example = PROJECT_ROOT / "config.example.json"
        if example.exists():
            import shutil
            shutil.copy(example, cfg_path)
            print("  [OK] config.json created from config.example.json")
        else:
            print("  [WARN] config.example.json not found")
    else:
        print("  [OK] config.json already exists")

    cfg_data = _load_project_config()

    print()
    print("  Initializing database...")
    try:
        from scripts.init_db import init_db as db_init
        db_path = resolve_path(PROJECT_ROOT, cfg_data.get("db_path", "./data/novel_memory.db"))
        schema = PROJECT_ROOT / "database" / "schema.sql"
        if not schema.exists():
            print("  [WARN] schema.sql not found, skipping DB init")
        else:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_init(str(db_path), str(schema))
            print(f"  [OK] Database initialized: {db_path}")
    except Exception as e:
        print(f"  [WARN] DB init error: {e}")

    dirs = [
        cfg_data.get("novels_root", "./novels"),
        cfg_data.get("outputs_root", "./outputs"),
        str(Path(cfg_data.get("outputs_root", "./outputs")) / "task_cards"),
        str(Path(cfg_data.get("outputs_root", "./outputs")) / "reviews"),
        cfg_data.get("exports_root", "./exports"),
        cfg_data.get("reports_root", "./exports/reports"),
        cfg_data.get("tmp_root", "./tmp"),
    ]
    for d in dirs:
        p = resolve_path(PROJECT_ROOT, d)
        p.mkdir(parents=True, exist_ok=True)
        print(f"  [OK] Directory ready: {p.relative_to(PROJECT_ROOT) if p.is_relative_to(PROJECT_ROOT) else p}")

    print()
    print("  Project initialized. Run 'python novel.py demo' to test.")
    return 0


def cmd_genre(args):
    """Genre pack management."""
    action = getattr(args, "genre_action", None)
    if action == "list":
        from scripts.genre.genre_loader import list_genres
        genres = list_genres()
        print(f"Available genres ({len(genres)}):")
        for g in genres:
            print(f"  {g}")
    elif action == "show":
        from scripts.genre.genre_loader import load_genre_pack
        gid = getattr(args, "genre_id", "generic")
        pack = load_genre_pack(gid)
        print(f"Genre: {pack.get('name', gid)} ({pack.get('genre_id', gid)})")
        print(f"  {pack.get('description', '')[:100]}")
        for key in ["core_promises", "forbidden_patterns", "agent_focus"]:
            items = pack.get(key, [])
            if items:
                print(f"  {key}:")
                for item in items[:5]:
                    print(f"    - {item}")
    else:
        print("Usage: python novel.py genre {list|show <id>}")
    return 0


def cmd_style(args):
    """Style pack management."""
    action = getattr(args, "style_action", None)
    if action == "list":
        from scripts.genre.style_loader import list_styles
        styles = list_styles()
        print(f"Available styles ({len(styles)}):")
        for s in styles:
            print(f"  {s}")
    elif action == "show":
        from scripts.genre.style_loader import load_style_pack
        sid = getattr(args, "style_id", "generic")
        pack = load_style_pack(sid)
        print(f"Style: {pack.get('name', sid)} ({pack.get('style_id', sid)})")
        print(f"  {pack.get('description', '')[:100]}")
        for key in ["narrative_features", "forbidden_patterns", "agent_focus"]:
            items = pack.get(key, [])
            if items:
                print(f"  {key}:")
                for item in items[:5]:
                    print(f"    - {item}")
    else:
        print("Usage: python novel.py style {list|show <id>}")
    return 0
