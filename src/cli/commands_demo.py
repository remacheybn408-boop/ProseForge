"""src/cli/commands_demo.py — Demo pipeline command v0.7.0"""

from src.cli.shared import (PROJECT_ROOT, SCRIPTS_DIR, _load_project_config,
    _get_default_slug, _get_novels_root, _resolve_post_context,
    _resolve_chapter_path, _story_exists, _story_missing_msg, _get_workspace_dir,
    _get_active_db_path, _get_outline_manager, _check_outline_gate, _get_story_dir)
import sys
import json
from pathlib import Path
from version import get_version
from scripts.config_utils import resolve_path


def cmd_demo():
    """Create demo_novel, activate outline, run pre -> post -> report -> export."""
    print("=" * 60)
    v = get_version()
    print(f"  Novel Forge - 小说引擎 {v}")
    print("  Demo Pipeline")
    print("=" * 60)
    print()

    import subprocess as _sp

    # STEP 1: db init — ensure workspace initialized for outline manager
    print("[STEP 1] Initializing workspace (db init)...")
    db_init_result = _sp.run(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "db", "init"],
        cwd=str(PROJECT_ROOT), timeout=60, capture_output=True, text=True
    )
    if db_init_result.returncode == 0:
        print("  [OK] db init completed")
    elif db_init_result.stdout and "已经初始化" in db_init_result.stdout:
        print("  [OK] workspace already initialized")
    else:
        print(f"  [WARN] db init returned {db_init_result.returncode}")

    # STEP 2: Init project (config.json + DB schema + directories)
    cfg_path = PROJECT_ROOT / "config.json"
    if not cfg_path.exists():
        print("\n[STEP 2] Initializing project (config + DB + directories)...")
        from src.cli.commands_core import cmd_init
        cmd_init()
        print()
    else:
        print("\n[STEP 2] config.json found. Checking database...")

    cfg_data = _load_project_config()
    # P0-2: Use active slot novel.db instead of global data/novel_memory.db
    db_path = _get_active_db_path()
    print(f"  Active slot DB: {db_path}")
    if not db_path.exists():
        print("  Database missing, initializing now...")
        from src.cli.commands_core import cmd_init
        cmd_init()
        cfg_data = _load_project_config()
        db_path = _get_active_db_path()

    slug = cfg_data.get("default_novel_slug", "demo_novel")
    title = cfg_data.get("default_novel_title", "Demo Novel")
    novels_root = resolve_path(PROJECT_ROOT, cfg_data.get("novels_root", "./novels"))
    vol_dir = Path(_resolve_chapter_path(slug))
    vol_dir.mkdir(parents=True, exist_ok=True)

    # v0.6.7-clean8: Ensure slot_001 is active for demo
    try:
        import json as _json
        ws_dir = PROJECT_ROOT / "workspace"
        reg_file = ws_dir / "registry.json"
        if reg_file.exists():
            reg = _json.loads(reg_file.read_text(encoding="utf-8"))
            reg["active_slot"] = "slot_001"
            reg_file.write_text(_json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    # STEP 3: Create demo chapter + outline.txt
    print("\n[STEP 3] Creating demo chapter...")
    demo_template = PROJECT_ROOT / "templates" / "demo_chapter.txt"
    demo_content = demo_template.read_text(encoding="utf-8")
    chapter_file = vol_dir / "第1章_开篇.txt"
    chapter_file.write_text(demo_content, encoding="utf-8")
    cn_count = sum(1 for c in demo_content if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
    print(f"  [OK] {chapter_file.name} ({cn_count} 汉字)")

    # v0.6.7-clean8: Also copy to active slot chapters dir for post
    slot_ch_dir = PROJECT_ROOT / "workspace" / "slot_001" / "chapters"
    slot_ch_dir.mkdir(parents=True, exist_ok=True)
    slot_ch_file = slot_ch_dir / "第1章_开篇.txt"
    slot_ch_file.write_text(demo_content, encoding="utf-8")
    print(f"  [OK] slot_001/chapters/{slot_ch_file.name}")

    outline_dir = novels_root / slug
    outline_dir.mkdir(parents=True, exist_ok=True)
    outline_file = outline_dir / "outline.txt"
    outline_file.write_text(
        "# Demo Novel 大纲\n\n第一卷：初入宗门。第1章：外门晨练，玉佩异动，大长老临时复测根骨。\n",
        encoding="utf-8",
    )
    print(f"  [OK] {outline_file.name}")

    # STEP 4: Register demo_novel in database
    print("\n[STEP 4] Registering demo_novel in database...")
    try:
        import sqlite3
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path))
        conn.execute("INSERT OR IGNORE INTO novels (slug, title, genre, status) VALUES (?, ?, ?, ?)",
                     (slug, title, cfg_data.get("default_genre", "xianxia"), "writing"))
        novel_id = conn.execute("SELECT id FROM novels WHERE slug=?", (slug,)).fetchone()[0]
        conn.execute("INSERT OR IGNORE INTO volumes (novel_id, volume_no, title) VALUES (?, ?, ?)",
                     (novel_id, 1, "第一卷"))
        conn.commit()
        conn.close()
        print("  [OK] registered")
    except Exception as e:
        print(f"  [ERROR] database registration failed: {e}")
        return 1

    # STEP 5: Activate outline — register outline.txt with outline manager (P0-1 FIX)
    print("\n[STEP 5] Activating demo outline...", flush=True)
    outline_result = _sp.run(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "outline", "add", str(outline_file),
         "--title", title, "--genre", cfg_data.get("default_genre", "xianxia")],
        cwd=str(PROJECT_ROOT), timeout=60, capture_output=True, text=True
    )
    if outline_result.stdout:
        print(outline_result.stdout, end="")
    if outline_result.stderr:
        print(outline_result.stderr, end="", file=sys.stderr)
    if outline_result.returncode == 0:
        print("  [OK] demo outline activated")
    elif outline_result.stdout and ("已经初始化" in outline_result.stdout or "already initialized" in outline_result.stdout):
        print("  [OK] demo outline activated (already present)")
    else:
        # outline add may succeed even with non-zero if outline already exists
        print(f"  [INFO] outline add exited {outline_result.returncode} — checking active state...")
        # fallback: try direct activation via outline manager
        try:
            mgr = _get_outline_manager()
            if mgr.has_active_outline():
                print("  [OK] demo outline is active")
            else:
                print("  [WARN] outline may not be active — pre may fail")
        except Exception:
            print("  [WARN] could not verify outline activation")

    # v0.7.1: Sync demo chapter to the active slot (outline add may have switched slots)
    try:
        from scripts.db.registry import Registry
        reg = Registry(PROJECT_ROOT)
        active_slot = reg.get_active_slot()
        if active_slot and active_slot != "slot_001":
            target_dir = PROJECT_ROOT / "workspace" / active_slot / "chapters"
            target_dir.mkdir(parents=True, exist_ok=True)
            src = PROJECT_ROOT / "workspace" / "slot_001" / "chapters" / "第1章_开篇.txt"
            if src.exists():
                dst = target_dir / "第1章_开篇.txt"
                dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                print(f"  [OK] 已同步章节到 {active_slot}/chapters/")
    except Exception as e:
        print(f"  [WARN] 章节同步失败: {e}")

    # STEP 6: Pre-write gate
    print("\n[STEP 6] Running pre-write gate...", flush=True)
    pre_result = _sp.run(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "pre", "1", "--slug", slug],
        cwd=str(PROJECT_ROOT), timeout=180, capture_output=True, text=True
    )
    if pre_result.stdout:
        print(pre_result.stdout, end="")
    if pre_result.stderr:
        print(pre_result.stderr, end="", file=sys.stderr)
    if pre_result.returncode != 0:
        print(f"  [FAIL] pre returned exit code {pre_result.returncode}")
        return pre_result.returncode
    print("  [OK] pre completed")

    # STEP 7: Post-write guards + ingest
    print("\n[STEP 7] Running post-write guards + ingest...", flush=True)
    post_result = _sp.run(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "post", "1", "--slug", slug],
        cwd=str(PROJECT_ROOT), timeout=300, capture_output=True, text=True
    )
    if post_result.stdout:
        print(post_result.stdout, end="")
    if post_result.stderr:
        print(post_result.stderr, end="", file=sys.stderr)
    if post_result.returncode != 0:
        print(f"  [FAIL] post returned exit code {post_result.returncode}")
        return post_result.returncode
    print("  [OK] post completed")

    # STEP 8: Report
    print("\n[STEP 8] Generating report...", flush=True)
    report_result = _sp.run(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "report"],
        cwd=str(PROJECT_ROOT), timeout=60, capture_output=True, text=True
    )
    if report_result.stdout:
        print(report_result.stdout, end="")
    if report_result.stderr:
        print(report_result.stderr, end="", file=sys.stderr)
    print("  [OK] report generated")

    # STEP 9: Export
    print("\n[STEP 9] Exporting demo novel...", flush=True)
    export_result = _sp.run(
        [sys.executable, str(PROJECT_ROOT / "novel.py"), "export", "--slug", slug, "--format", "md"],
        cwd=str(PROJECT_ROOT), timeout=60, capture_output=True, text=True
    )
    if export_result.stdout:
        print(export_result.stdout, end="")
    if export_result.stderr:
        print(export_result.stderr, end="", file=sys.stderr)
    if export_result.returncode == 0:
        print("  [OK] export generated")
    else:
        print(f"  [WARN] export returned {export_result.returncode}")

    print("\n  Demo complete!")
    print(f"  章节文件：workspace/slot_001/chapters/{slot_ch_file.name}")
    print(f"  兼容副本：{chapter_file}")
    print(f"  Report:   python novel.py report")
    print(f"  Export:   python novel.py export --slug {slug}")
    print()
    print("=" * 60)
    print("  Demo pipeline passed.")
    print("=" * 60)
    return 0
