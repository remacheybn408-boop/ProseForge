#!/usr/bin/env python3
"""
novel.py — Novel Pipeline Write Engine CLI v0.6.5

Top-level entry point wrapping chapter_pipeline, doctor, report, db tools.

Usage:
  python novel.py status [--detail]   Run environment diagnostics
  python novel.py doctor [--detail]   Same as status --detail (alias)
  python novel.py demo                Run demo (pre for chapter 1)
  python novel.py report              Show most recent guard reports
  python novel.py guards              List registered guards and status
  python novel.py check <file>        Run guard checks on a chapter file
  python novel.py db <command>        Multi-DB workspace management
"""

import sys
from version import get_version
import json
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
SRC_GUARDS_DIR = PROJECT_ROOT / "src" / "guards"

# Ensure scripts dir is importable
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SRC_GUARDS_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_GUARDS_DIR))

from config_utils import normalize_config, load_json_config, resolve_path


def _load_project_config() -> dict:
    """Load config.json/config.example.json using the shared compatibility layer."""
    cfg_path = PROJECT_ROOT / "config.json"
    if cfg_path.exists():
        return load_json_config(cfg_path, PROJECT_ROOT)
    return load_json_config(PROJECT_ROOT / "config.example.json", PROJECT_ROOT)


def _cfg_path(key: str, default: str) -> Path:
    cfg = _load_project_config()
    return resolve_path(PROJECT_ROOT, cfg.get(key, default))


def cmd_status(detail=False):
    """Run doctor.py for environment diagnostics. --detail for verbose output."""
    print("=" * 60)
    v = get_version()
    print(f"  Novel Pipeline - Write Engine {v}")
    mode_str = "详细" if detail else "标准"
    print(f"  状态检查 ({mode_str})")
    print("=" * 60)
    print()

    try:
        from doctor import main as doctor_main
        return doctor_main(detail=detail)
    except ImportError:
        # Fallback manual check
        print("  Running manual status check...")
        all_ok = True
        import platform as _platform

        # OS
        _os = _platform.system()
        ok = True
        print(f"  [OK] OS: {_os} {_platform.release()}")

        # Python version
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
        ok = sys.version_info >= (3, 10)
        mark = "OK" if ok else "FAIL"
        print(f"  [{mark}] Python {py_ver}")
        all_ok &= ok

        # config.json
        cfg = PROJECT_ROOT / "config.json"
        ok = cfg.exists()
        mark = "OK" if ok else "MISSING"
        print(f"  [{mark}] config.json")
        all_ok &= ok

        # src/guards/
        ok = (SRC_GUARDS_DIR / "reader_pull_guard.py").exists()
        mark = "OK" if ok else "MISSING"
        print(f"  [{mark}] src/guards/reader_pull_guard.py")
        all_ok &= ok

        ok = (SRC_GUARDS_DIR / "voice_pack_guard.py").exists()
        mark = "OK" if ok else "MISSING"
        print(f"  [{mark}] src/guards/voice_pack_guard.py")
        all_ok &= ok

        ok = (SRC_GUARDS_DIR / "meme_pack_guard.py").exists()
        mark = "OK" if ok else "MISSING"
        print(f"  [{mark}] src/guards/meme_pack_guard.py")
        all_ok &= ok

        # voice_packs
        vp = PROJECT_ROOT / "voice_packs"
        ok = vp.exists()
        mark = "OK" if ok else "MISSING"
        print(f"  [{mark}] voice_packs/ directory")
        all_ok &= ok

        if all_ok:
            print("\n  All checks passed. Ready to write.")
        else:
            print("\n  Some checks failed. Run install.bat first.")

        return 0 if all_ok else 1


def cmd_doctor(detail=True):
    """Alias for status with --detail by default."""
    return cmd_status(detail=detail)


def cmd_demo():
    """Create demo_novel, activate outline, run pre -> post -> report -> export."""
    print("=" * 60)
    v = get_version()
    print(f"  Novel Pipeline - Write Engine {v}")
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
        cmd_init()
        cfg_data = _load_project_config()
        db_path = _get_active_db_path()

    slug = cfg_data.get("default_novel_slug", "demo_novel")
    title = cfg_data.get("default_novel_title", "Demo Novel")
    novels_root = resolve_path(PROJECT_ROOT, cfg_data.get("novels_root", "./novels"))
    vol_dir = novels_root / slug / "第01卷"
    vol_dir.mkdir(parents=True, exist_ok=True)

    # v0.6.5-clean8: Ensure slot_001 is active for demo
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
    paragraphs = [
        "第1章 开篇",
        "清晨的钟声从青云宗山腰传来，像一根细线，把外门弟子从浅睡里一一拽醒。李明远坐在窄床边，先没有急着穿鞋，而是低头看向掌心那枚旧玉佩。玉佩的边缘有一道细裂，裂纹像凝住的水波，三年来从未扩大，也从未消失。",
        "他来到青云宗已经第三年。三年前，他还只是海边渔村里的少年，每天跟着父亲补网、看潮、记风向。那场暴风雨把渔船掀翻时，他以为自己会沉进海底，偏偏胸口的玉佩发出一点冷光，把他推上了岸，也把他推到了修行人的门槛前。",
        "门外传来小石头的声音：\"远哥，王教习让我们提前到练功场，说今日有长老巡视。\"小石头说话总带着一点慌张，像随时准备把自己缩进墙角。他本名石磊，因为个子小，入门又晚，所有人都叫他小石头，只有李明远还会认真叫他一声师弟。",
        "李明远把玉佩塞回衣襟，推门出去。晨雾还没有散，练功场的青砖上凝着水汽，几十名外门弟子已经排成三列。有人在压腿，有人默背心法，也有人趁王教习没到，偷偷用余光打量山道尽头。今日的气氛很不对，连平日爱说笑的赵铁柱都闭着嘴，双手按在膝上，一下一下调整呼吸。",
        "王教习终于来了。他须发皆白，步子却稳，木杖点在砖面上，声声清脆。\"今日大长老巡视外门，谁若在基础功上偷奸耍滑，老夫先罚，戒律堂再罚。\"这句话不重，却让人背脊发紧。外门弟子最怕的不是挨骂，而是被记入戒律堂的黑册，一旦名字落上去，日后进内门几乎无望。",
        "赵铁柱压低声音道：\"明远，你昨晚是不是又练到后半夜？脸色不太对。\"李明远摇摇头，没有解释。他昨夜确实没睡好，但不是因为修炼，而是因为玉佩第一次在无人触碰时自己发热。那股热意顺着胸口往丹田走，像有人在他体内画了一条陌生的经脉路线。",
        "王教习开始点名。每点到一人，便让其演示三式基础剑法。轮到李明远时，周围忽然安静下来。他的修为只是炼气三层，算不上拔尖，可他的剑路总有些古怪，明明用的是最普通的青云十三式，落点却比旁人更准，像每一剑都提前知道风会往哪里吹。",
        "李明远握住木剑，第一式平平推出。剑尖划过雾气，雾线被割开，又在他身后缓慢合拢。第二式转腕时，他胸前玉佩忽然一烫，丹田里的真气不受控制地偏了半寸。只是半寸，木剑却发出一声轻鸣，练功场边的铜铃无风自响。",
        "所有人都愣住了。王教习的眼神骤然锐利，大步走到李明远面前，伸手扣住他的腕脉。李明远只觉得一股外来的灵力沿着手腕探入体内，还没碰到玉佩所在的位置，就被一层冰冷的阻力挡了回去。王教习脸色微变，随即松手，低声道：\"今日之后，你不要一个人去后山。\"",
        "这句话来得突兀，小石头吓得脸都白了。赵铁柱想问，却被王教习一个眼神压回去。李明远心里那点不安终于落成了实物：不是他多想，玉佩真的被人察觉了。更糟的是，察觉的人未必只有王教习。",
        "山道上，三名内门弟子簇拥着一位青袍老者缓缓走来。老者眉目清瘦，袖口绣着戒律堂的玄色云纹，正是外门弟子口中最不愿遇见的大长老。他的目光扫过练功场，最后停在李明远身上，停得比任何人都久。",
        "李明远低下头，手指按住衣襟里的玉佩。玉佩已经恢复冰凉，可那道裂纹里似乎多了一点极淡的金色。它像一只刚睁开的眼睛，在沉默里看着所有人。",
        "大长老没有立刻说话，只是对王教习点了点头。王教习会意，宣布今日晨练改为根骨复测。人群顿时骚动起来。根骨复测一年一次，通常只为筛选升入内门的弟子，绝不会临时提前。李明远听见身后有人倒吸冷气，也听见小石头小声念了一句：\"完了，肯定有人要倒霉。\"",
        "李明远没有回头。他知道那个人很可能就是自己。可他也清楚，若今日退缩，玉佩的秘密未必能保住，自己的路也会被别人安排。三年来，他第一次生出一个明确的念头：他不能再只做外门里那个安静听话的弟子。",
        "铜铃第二次响起时，雾气终于散开。阳光落在练功场中央，也落在大长老面前那块测灵石上。李明远向前一步，掌心贴上冰冷的石面。下一瞬，测灵石深处亮起一道从未在外门出现过的青金色细线，像雷光，也像裂开的命运。",
    ]
    demo_content = "\n\n".join(paragraphs) + "\n"
    chapter_file = vol_dir / "第1章_开篇.txt"
    chapter_file.write_text(demo_content, encoding="utf-8")
    cn_count = sum(1 for c in demo_content if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
    print(f"  [OK] {chapter_file.name} ({cn_count} 汉字)")

    # v0.6.5-clean8: Also copy to active slot chapters dir for post
    slot_ch_dir = PROJECT_ROOT / "workspace" / "slot_001" / "chapters"
    slot_ch_dir.mkdir(parents=True, exist_ok=True)
    slot_ch_file = slot_ch_dir / "第1章_开篇.txt"
    slot_ch_file.write_text(demo_content, encoding="utf-8")
    print(f"  [OK] slot_001/chapters/{slot_ch_file.name}")

    outline_file = novels_root / slug / "outline.txt"
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
    print(f"  Chapter:  {chapter_file}")
    print(f"  Report:   python novel.py report")
    print(f"  Export:   python novel.py export --slug {slug}")
    print()
    print("=" * 60)
    print("  Demo pipeline passed.")
    print("=" * 60)
    return 0

def cmd_report():
    """Show most recent guard reports and exports."""
    print("=" * 60)
    v = get_version()
    print(f"  Novel Pipeline - Write Engine {v}")
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
    print(f"  Novel Pipeline - Write Engine {v}")
    print("  Guard Registry")
    print("=" * 60)
    print()

    # Core guards from registry
    print("  [Core Guards — scripts/]")
    try:
        from guard_registry import GUARD_RUNNERS, GUARD_LEVELS, MODE_GUARDS
        for name in sorted(GUARD_RUNNERS):
            level = GUARD_LEVELS.get(name, "?")
            print(f"    L{level} {name}")
    except ImportError:
        print("    (guard_registry not importable)")

    print()
    print("  [v0.5.0 Guards — src/guards/]")
    v050_guards = ["reader_pull_guard", "voice_pack_guard", "meme_pack_guard"]
    for name in v050_guards:
        fp = SRC_GUARDS_DIR / f"{name}.py"
        exists = "OK" if fp.exists() else "MISSING"
        print(f"    [{exists}] {name}")

    print()
    print("  [Guard Modes]")
    try:
        from guard_registry import MODE_GUARDS
        for mode, guards in MODE_GUARDS.items():
            print(f"    {mode}: {len(guards)} guards")
    except ImportError:
        pass

    print()
    return 0


def cmd_check(file_path: str):
    """Run v0.5.0 guards on a chapter file."""
    fp = Path(file_path)
    if not fp.exists():
        print(f"[ERROR] File not found: {fp}")
        return 1

    content = fp.read_text(encoding="utf-8")
    print("=" * 60)
    print(f"  Checking: {fp.name}")
    print("=" * 60)
    print()

    # Reader pull guard
    print("--- reader_pull_guard ---")
    try:
        from src.guards.reader_pull_guard import run_reader_pull_check
        rp_report = run_reader_pull_check(content, chapter_no=1)
        status = rp_report["status"]
        issues = len(rp_report.get("issues", []))
        print(f"  Status: {status} ({issues} issues)")
        if issues:
            for iss in rp_report.get("issues", [])[:5]:
                print(f"    [{iss['code']}] {iss['message'][:80]}")
    except ImportError as e:
        print(f"  [WARN] reader_pull_guard not available: {e}")
    except Exception as e:
        print(f"  [WARN] reader_pull_guard error: {e}")

    print()

    # Voice pack guard
    print("--- voice_pack_guard ---")
    try:
        from src.guards.voice_pack_guard import run_voice_pack_check
        vp_dir = str(PROJECT_ROOT / "voice_packs")
        vp_report = run_voice_pack_check(content, chapter_no=1, voice_packs_dir=vp_dir)
        status = vp_report["status"]
        issues = len(vp_report.get("issues", [])) or len(vp_report.get("warnings", []))
        print(f"  Status: {status} ({issues} issues)")
        extra = vp_report.get("extra_checks", {})
        for check_name, check_issues in extra.items():
            if check_issues:
                print(f"    {check_name}: {len(check_issues)} issues")
    except ImportError as e:
        print(f"  [WARN] voice_pack_guard not available: {e}")
    except Exception as e:
        print(f"  [WARN] voice_pack_guard error: {e}")

    print()

    # Meme pack guard
    print("--- meme_pack_guard ---")
    try:
        from src.guards.meme_pack_guard import run_meme_pack_check
        mp_dir = str(PROJECT_ROOT / "voice_packs")
        mp_report = run_meme_pack_check(content, chapter_no=1, meme_packs_dir=mp_dir)
        status = mp_report["status"]
        issues = len(mp_report.get("issues", []))
        print(f"  Status: {status} ({issues} issues)")
        for iss in mp_report.get("issues", [])[:5]:
            print(f"    [{iss['code']}] {iss['message'][:80]}")
    except ImportError as e:
        print(f"  [WARN] meme_pack_guard not available: {e}")
    except Exception as e:
        print(f"  [WARN] meme_pack_guard error: {e}")

    print()
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
            slug = cfg_data.get("default_novel_slug", "demo_novel")
            novels_root = resolve_path(PROJECT_ROOT, cfg_data.get("novels_root", "./novels"))
            ch_dir = Path(novels_root) / slug / "第01卷"
            candidates = list(ch_dir.glob(f"第{chapter_no}章*.txt"))
            if not candidates:
                candidates = list(ch_dir.glob(f"第{chapter_no:02d}章*.txt"))
            if candidates:
                fp = candidates[0]
            else:
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
    print(f"  Novel Pipeline - Write Engine {v}")
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
        from init_db import init_db as db_init
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

def _get_default_slug(cfg_path=None):
    """Resolve default novel slug from config.json."""
    try:
        return _load_project_config().get("default_novel_slug", "demo_novel")
    except Exception:
        return "demo_novel"


def cmd_pre(chapter_no: str = None, slug: str = None, volume_no: str = None):
    """Run pre-write gate for a chapter."""
    cfg = PROJECT_ROOT / "config.json"
    if not chapter_no:
        print("Usage: python novel.py pre <chapter_no> [--slug <slug>] [--volume <n>]")
        return 1
    # No-outline gate
    if _check_outline_gate():
        return 1
    print(f"  Running pre-write gate for chapter {chapter_no}...")
    # v0.6.5-clean7: resolve slug from active slot
    chapters_dir, slot_db_path, resolved_slug, resolved_title = _resolve_post_context(cfg)
    slug = slug or resolved_slug
    try:
        import subprocess
        cmd = [sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "pre", str(chapter_no),
               "--config", str(cfg), "--novel-slug", slug,
               "--novel-title", resolved_title]
        if volume_no: cmd.extend(["--volume-no", str(volume_no)])
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), timeout=120)
        return result.returncode
    except Exception as e:
        print(f"  [ERROR] {e}")
        return 1


def cmd_post(chapter_no: str = None, slug: str = None, volume_no: str = None, file_path: str = None, story: bool = False):
    """Post-write: run guards and ingest."""
    cfg = PROJECT_ROOT / "config.json"
    if not chapter_no and not file_path:
        print("Usage: python novel.py post <chapter_no> [--file <path>] [--slug <slug>] [--story]")
        return 1
    # No-outline gate
    if _check_outline_gate():
        return 1
    if file_path:
        print(f"  Running post-write guards for file: {file_path}")
    else:
        print(f"  Running post-write guards for chapter {chapter_no}...")

    # v0.6.5-clean6: Resolve from active slot, fallback to config
    chapters_dir, slot_db_path, resolved_slug, resolved_title = _resolve_post_context(cfg)
    slug = slug or resolved_slug

    try:
        import subprocess
        cmd = [sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "post",
               str(chapter_no) if chapter_no else "1",
               "--config", str(cfg), "--novel-slug", slug]
        if volume_no: cmd.extend(["--volume-no", str(volume_no)])
        if file_path:
            cmd.extend(["--chapters-dir", str(Path(file_path).parent)])
        else:
            cmd.extend(["--chapters-dir", chapters_dir])
        if slot_db_path:
            cmd.extend(["--db-path", slot_db_path])
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), timeout=300)
        if result.returncode != 0:
            return result.returncode

        # Auto-generate story commit if --story flag is set and .story/ exists
        if story and _story_exists():
            print()
            print("  [story] 自动生成提交记录...")
            try:
                from scripts.story import commit_builder
                ch_no = int(chapter_no) if chapter_no else 1

                # Try to read word count from the chapter file
                wc = 0
                if file_path:
                    ch_fp = Path(file_path)
                else:
                    novels_root = _get_novels_root(cfg)
                    ch_dir = Path(novels_root) / slug / "第01卷"
                    candidates = list(ch_dir.glob(f"第{ch_no}章*.txt"))
                    ch_fp = candidates[0] if candidates else None

                if ch_fp and ch_fp.exists():
                    text = ch_fp.read_text(encoding="utf-8")
                    wc = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')

                # Try reading guard report for summary
                guard_summary = {}
                try:
                    import json as _json
                    cfg_data = _load_project_config()
                    reports_dir = resolve_path(PROJECT_ROOT, cfg_data.get("reports_root", "./exports/reports"))
                    if reports_dir.exists():
                        reports = sorted(reports_dir.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
                        if reports:
                            rpt = _json.loads(reports[0].read_text(encoding="utf-8"))
                            guard_summary = {
                                "status": rpt.get("status", rpt.get("overall_status", "?")),
                                "issues": len(rpt.get("issues", [])),
                            }
                except Exception:
                    pass

                commit = commit_builder.build_commit(
                    PROJECT_ROOT, ch_no,
                    chapter_title=f"第{ch_no}章",
                    word_count=wc,
                    guard_summary=guard_summary,
                )
                saved = commit_builder.save_commit(PROJECT_ROOT, ch_no, commit)
                print(f"  [story] 第{ch_no}章提交记录已保存: {Path(saved).name}")
            except Exception as e:
                print(f"  [story] 提交生成失败: {e}")

        return result.returncode
    except Exception as e:
        print(f"  [ERROR] {e}")
        return 1


def _get_novels_root(cfg_path=None):
    """Read novels_root from config."""
    try:
        cfg = _load_project_config()
        return str(resolve_path(PROJECT_ROOT, cfg.get("novels_root", "./novels")))
    except Exception:
        return str(PROJECT_ROOT / "novels")


def _get_outline_dir():
    """v0.6.5-clean7: 大纲目录 = novels_root 的同级 大纲/."""
    nr = Path(_get_novels_root())
    return str(nr.parent / "大纲")


def _resolve_post_context(cfg):
    """v0.6.5-clean7: Resolve chapters_dir + db_path + slug + title from active slot.
    Returns (chapters_dir, db_path, slug, title). Falls back to config defaults.
    """
    import json as _json
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"

    if reg_file.exists():
        try:
            reg = _json.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            if active:
                slot_dir = ws / active
                ch_dir = slot_dir / "chapters"
                db_path = slot_dir / "novel.db"
                if db_path.exists():
                    import sqlite3 as _sql
                    conn = _sql.connect(str(db_path))
                    try:
                        row = conn.execute("SELECT slug, title FROM novels LIMIT 1").fetchone()
                        slug = row[0] if row else _get_default_slug(cfg)
                        title = row[1] if row and row[1] else slug
                    except Exception:
                        slug = _get_default_slug(cfg)
                        title = slug
                    finally:
                        conn.close()
                    return str(ch_dir), str(db_path), slug, title
        except Exception:
            pass

    # Fallback: old config-based paths
    slug = _get_default_slug(cfg)
    novels_root = _get_novels_root(cfg)
    return str(Path(novels_root) / slug / "第01卷"), None, slug, slug


def cmd_review(chapter_no: str = None, slug: str = None, volume_no: str = None):
    """Run guard review on a chapter."""
    cfg = PROJECT_ROOT / "config.json"
    if not chapter_no:
        print("Usage: python novel.py review <chapter_no> [--slug <slug>] [--volume <n>]")
        return 1
    print(f"  Running review for chapter {chapter_no}...")
    slug = slug or _get_default_slug(cfg)
    try:
        import subprocess
        cmd = [sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "review", str(chapter_no),
               "--config", str(cfg), "--novel-slug", slug]
        if volume_no: cmd.extend(["--volume-no", str(volume_no)])
        result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), timeout=300)
        return result.returncode
    except Exception as e:
        print(f"  [ERROR] {e}")
        return 1


def cmd_export(slug: str = None, fmt: str = "md"):
    """Export novel to a single file, v0.6.5-clean7: 用小说名建文件夹."""
    # v0.6.5-clean7: 无slug时自动从活跃slot读取
    if not slug:
        try:
            import json as _j, sqlite3 as _s
            ws = PROJECT_ROOT / "workspace"
            reg = _j.loads((ws / "registry.json").read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            slot_db = ws / active / "novel.db"
            if slot_db.exists():
                conn = _s.connect(str(slot_db))
                row = conn.execute("SELECT slug FROM novels LIMIT 1").fetchone()
                conn.close()
                if row:
                    slug = row[0]
        except Exception:
            pass
    if not slug:
        print("用法: python novel.py export [--slug <标识>] [--format txt|md]")
        print()
        print("  示例:")
        print("    python novel.py export --slug demo_novel --format md")
        print("    python novel.py export --slug demo_novel --format txt")
        return 1
    fmt = fmt or "md"
    ext = ".txt" if fmt == "txt" else ".md"

    # v0.6.5-clean7: 从活跃 slot DB 读取标题 + DB 路径
    import sqlite3 as _sql
    title = slug
    slot_db_path = None
    try:
        ws = PROJECT_ROOT / "workspace"
        reg_file = ws / "registry.json"
        if reg_file.exists():
            import json as _json
            reg = _json.loads(reg_file.read_text(encoding="utf-8"))
            active = reg.get("active_slot", "")
            slot_db = ws / active / "novel.db"
            if slot_db.exists():
                slot_db_path = slot_db
                conn = _sql.connect(str(slot_db))
                row = conn.execute("SELECT title FROM novels WHERE slug=?", (slug,)).fetchone()
                if row:
                    title = row[0]
                conn.close()
    except Exception:
        pass

    # 输出到小说自己的文件夹：novels_root/{书名}/{书名}.txt
    cfg = _load_project_config()
    nr = Path(_get_novels_root())
    out_dir = nr / title
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{title}{ext}"

    print(f"  正在导出小说「{title}」(slug={slug})，格式: {fmt}...")
    import subprocess
    try:
        args = [sys.executable, str(SCRIPTS_DIR / "export_novel.py"),
                "--slug", slug, "--config", str(PROJECT_ROOT / "config.json"), "--format", fmt,
                "--output", str(out_path)]
        if slot_db_path:
            args.extend(["--db-path", str(slot_db_path)])
        result = subprocess.run(args, cwd=str(PROJECT_ROOT), timeout=60, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        if result.returncode == 0:
            print(f"  ✅ 已导出全书到 {out_path}")
            # v0.6.5-clean7: 同时拆分每章为独立文件
            full_text = Path(out_path).read_text(encoding="utf-8")
            # Split by chapter headers: 第N章 or ---\n第N章
            import re as _re
            parts = _re.split(r'\n(?=第\d+章\s)', full_text)
            count = 0
            for part in parts:
                m = _re.match(r'第(\d+)章\s+(.+)', part.strip())
                if m:
                    ch_num = int(m.group(1))
                    ch_title = m.group(2).strip().split('\n')[0][:20]
                    ch_file = out_dir / f"第{ch_num}章_{ch_title}.txt"
                    ch_file.write_text(part.strip() + "\n", encoding="utf-8")
                    count += 1
            if count:
                print(f"  ✅ 已拆分 {count} 章到 {out_dir}/")
        else:
            print(f"  ⚠️ 导出未完成（退出码: {result.returncode}）")
        return result.returncode
    except subprocess.TimeoutExpired:
        print(f"  ⏱️ 导出超时，请检查章节数量是否过多。")
        return 1
    except Exception as e:
        print(f"  ❌ 导出失败: {e}")
        return 1


def _cmd_agents_list(args):
    """List all available agent configurations with metadata."""
    import json as _json
    import yaml as _yaml

    agents_dir = PROJECT_ROOT / "configs" / "jury" / "agents"
    mode_filter = getattr(args, "mode", None) or ""

    if not agents_dir.exists():
        print("  No agent configurations found.")
        print(f"  Expected: {agents_dir}")
        return 1

    agent_files = sorted(agents_dir.glob("*.yaml"))
    if not agent_files:
        print("  No agent YAML files found.")
        return 0

    print("=" * 70)
    print(f"  Agent 陪审团 — {len(agent_files)} 个审查代理")
    print("=" * 70)
    print()

    # Load jury mode configs to show per-mode agents
    modes_dir = PROJECT_ROOT / "configs" / "jury"
    mode_agents = {}
    for mf in sorted(modes_dir.glob("jury.*.yaml")):
        try:
            mode_data = _yaml.safe_load(mf.read_text(encoding="utf-8"))
            mode_name = mode_data.get("mode", mf.stem.replace("jury.", ""))
            mode_agents[mode_name] = mode_data.get("agents", [])
        except Exception:
            pass

    for af in agent_files:
        try:
            data = _yaml.safe_load(af.read_text(encoding="utf-8"))
        except Exception:
            print(f"  {af.stem:30s} [无法解析]")
            continue

        agent_id = data.get("agent_id", af.stem)
        name = data.get("name", agent_id)
        category = data.get("category", "unknown")
        risk = data.get("risk_level", "medium")
        enabled = data.get("default_enabled", True)
        weight = data.get("weight", 1.0)
        desc = data.get("description", "")
        if len(desc) > 80:
            desc = desc[:77] + "..."

        # Which modes include this agent?
        in_modes = [m for m, ags in mode_agents.items() if agent_id in ags]

        status_icon = "✓" if enabled else "○"
        risk_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk, "⚪")

        print(f"  {status_icon} {risk_icon} {name:<24s} [{agent_id}]")
        print(f"     类别: {category:<15s} 权重: {weight:.1f}  模式: {','.join(in_modes) if in_modes else '(未分配)'}")
        print(f"     {desc}")
        print()

    print("-" * 70)
    print(f"  共 {len(agent_files)} 个代理   ✓=默认启用  ○=需手动启用")
    print(f"  🔴=高风险  🟡=中风险  🟢=低风险")
    print("=" * 70)
    return 0


def cmd_agents(args):
    """Multi-agent review board."""
    action = getattr(args, "agents_action", None)

    # agents list — show all available agents
    if action == "list":
        return _cmd_agents_list(args)

    if action != "review":
        print("Usage: python novel.py agents {list|review}")
        print("  list                     — 列出所有可用审查代理")
        print("  review <N> [--mode ...]  — 运行多Agent审稿")
        return 1
    chapter_no = getattr(args, "chapter_no", None)
    if not chapter_no:
        print("Usage: python novel.py agents review <chapter_no>")
        return 1
    try:
        import json as _json
        cfg_path = PROJECT_ROOT / "config.json"
        _cfg = {}
        if cfg_path.exists():
            _cfg = _load_project_config()
        slug = getattr(args, "slug", None) or _cfg.get("default_novel_slug", "demo_novel")
        novels_root = resolve_path(PROJECT_ROOT, _cfg.get("novels_root", "./novels"))
        ch_dir = Path(novels_root) / slug / "第01卷"
        candidates = list(ch_dir.glob(f"第{chapter_no}章*.txt"))
        if not candidates:
            print(f"[WARN] No chapter file found for chapter {chapter_no} in {ch_dir}")
            print(f"[INFO] Running agent review on empty context...")
            content = ""
        else:
            content = candidates[0].read_text(encoding="utf-8")
        
        mode = getattr(args, "mode", "light")
        print(f"Running {mode}-mode agent review for chapter {chapter_no}...")
        from scripts.agents.orchestrator import run_agent_review
        result = run_agent_review(content, int(chapter_no), mode=mode)
        print(f"  Score: {result.get('overall_score', 'N/A')}")
        print(f"  Status: {result.get('status', 'N/A')}")
        if result.get('status') == 'FAIL':
            print(f"  💡 审稿 FAIL ≠ 程序出错，是 AI 对内容质量的建议，可忽略")
        chief = result.get("chief_editor", {})
        for cat in ["must_fix", "should_fix", "keep"]:
            items = chief.get(cat, [])
            if items:
                print(f"  {cat}: {len(items)} items")
        return 0
    except Exception as e:
        print(f"  [ERROR] Agent review failed: {e}")
        return 1


def cmd_rag(args):
    """Vector RAG queries."""
    action = getattr(args, "rag_action", None)
    if action == "status":
        print("RAG Status:")
        try:
            from scripts.rag.rag_config import load_rag_config, get_rag_mode
            cfg = load_rag_config()
            mode = get_rag_mode(cfg)
            # Vector available if sentence_transformers is installed
            try:
                import sentence_transformers
                vector_ok = True
            except ImportError:
                vector_ok = False
            print(f"  Mode: {mode}")
            print(f"  Vector: {'available' if vector_ok else 'unavailable (fallback to FTS5)'}")
        except Exception as e:
            print(f"  FTS5: available (default)")
            print(f"  Vector: unavailable ({e})")
        return 0
    elif action == "query":
        question = " ".join(getattr(args, "question", []))
        if not question:
            print("Usage: python novel.py rag query <question>")
            return 1
        try:
            from scripts.rag.rag_query import rag_query
            result = rag_query(question)
            print(f"Query: {question}")
            print(f"Mode: {result.get('mode', 'fts5')}")
            for r in result.get("results", [])[:5]:
                print(f"  [{r.get('chapter_no', '?')}] {r.get('evidence', '')[:80]}")
        except Exception as e:
            print(f"  [WARN] RAG query unavailable: {e}")
        return 0
    else:
        print("Usage: python novel.py rag {status|query}")
        return 1


# ============================================================
#  Story Contract system commands
# ============================================================

def _story_exists() -> bool:
    """Check if .story/ directory is initialized."""
    return (PROJECT_ROOT / ".story").exists()


def _story_missing_msg() -> str:
    return "请先运行 python novel.py story init"


def cmd_story(args):
    """Story contract system: init, contract, commit, health."""
    from scripts.story import story_init, contract_builder, commit_builder, story_health

    action = getattr(args, "story_action", None)

    if action == "init":
        if _story_exists():
            print("  .story/ 目录已存在。如需重建请先删除。")
            return 0
        result = story_init.init_story(PROJECT_ROOT)
        print(f"  [OK] .story/ 已初始化")
        for item in result.get("created", []):
            print(f"    + {item}")
        print(f"\n  目录: {result['story_dir']}")
        return 0

    elif action == "contract":
        if not _story_exists():
            print(f"  {_story_missing_msg()}")
            return 1
        # No-outline gate
        if _check_outline_gate():
            return 1
        chapter_no = int(getattr(args, "chapter_no", "1") or "1")
        # Try loading previous commit for context
        prev_commit = None
        if chapter_no > 1:
            prev_commit_path = PROJECT_ROOT / ".story" / "commits" / f"chapter_{chapter_no-1:03d}_commit.json"
            if prev_commit_path.exists():
                import json as _json
                prev_commit = _json.loads(prev_commit_path.read_text(encoding="utf-8"))

        contract = contract_builder.build_contract(PROJECT_ROOT, chapter_no, prev_commit=prev_commit)
        saved = contract_builder.save_contract(PROJECT_ROOT, chapter_no, contract)
        print(f"  [OK] 第{chapter_no}章合同已生成")
        print(f"  保存至: {saved}")
        print(f"  开放伏笔: {len(contract.get('open_promises_to_keep', []))} 个")
        print(f"  活跃角色: {len(contract.get('active_characters', []))} 个")
        return 0

    elif action == "commit":
        if not _story_exists():
            print(f"  {_story_missing_msg()}")
            return 1
        chapter_no = int(getattr(args, "chapter_no", "1") or "1")
        
        # P0-2: Verify contract exists before allowing commit
        contract_path = PROJECT_ROOT / ".story" / "chapters" / f"chapter_{chapter_no:03d}_contract.json"
        if not contract_path.exists():
            print(f"  [FAIL] 第{chapter_no}章没有合同，不能提交。请先执行：python novel.py story contract {chapter_no}")
            return 1

        # Read real chapter file — use config's novels_root
        novels_dir = PROJECT_ROOT / "novels"
        if (PROJECT_ROOT / "config.json").exists():
            import json as _json
            try:
                cfg = _json.loads((PROJECT_ROOT / "config.json").read_text(encoding="utf-8"))
                nr = cfg.get("novels_root") or cfg.get("paths", {}).get("novels_root", "novels")
                novels_dir = Path(nr) if Path(nr).is_absolute() else PROJECT_ROOT / nr
            except: pass
        slug = "demo_novel"
        # Also try the config's default slug
        slugs_to_try = [slug]
        try:
            if (PROJECT_ROOT / "config.json").exists():
                cfg2 = _json.loads((PROJECT_ROOT / "config.json").read_text(encoding="utf-8"))
                ds = cfg2.get("default_novel_slug") or cfg2.get("novel", {}).get("default_slug", "")
                if ds and ds != slug:
                    slugs_to_try.append(ds)
        except: pass
        import re as _re
        ch_fp = None
        # Search multiple possible locations
        search_dirs = []
        for s in slugs_to_try:
            search_dirs.append(novels_dir / s / "第01卷")
            search_dirs.append(novels_dir / s)
            search_dirs.append(PROJECT_ROOT / "novels" / s / "第01卷")
        for sd in search_dirs:
            if not sd.exists(): continue
            for pattern in [f"第{chapter_no}章*.txt", f"第{chapter_no:02d}章*.txt"]:
                candidates = list(sd.glob(pattern))
                if candidates:
                    ch_fp = candidates[0]
                    break
            if ch_fp: break
        wc = 0
        ch_title = f"第{chapter_no}章"
        if ch_fp and ch_fp.exists():
            text = ch_fp.read_text(encoding="utf-8")
            wc = sum(1 for c in text if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
            ch_title = ch_fp.stem.replace("_", " ")
        
        commit = commit_builder.build_commit(
            PROJECT_ROOT, chapter_no,
            chapter_title=ch_title,
            word_count=wc,
            guard_summary={"note": "手动生成"} if wc == 0 else {},
        )
        saved = commit_builder.save_commit(PROJECT_ROOT, chapter_no, commit)
        print(f"  [OK] 第{chapter_no}章提交记录已生成")
        print(f"  保存至: {saved}")
        return 0

    elif action == "health":
        if not _story_exists():
            print(f"  {_story_missing_msg()}")
            return 1
        report = story_health.check_health(PROJECT_ROOT)
        print("=" * 60)
        print("  故事链健康检查")
        print("=" * 60)
        status = report["status"]
        print(f"  状态: {status}")
        print(f"  合同数: {report.get('contract_count', 0)}")
        print(f"  提交数: {report.get('commit_count', 0)}")
        print(f"  事件数: {report.get('event_count', 0)}")
        warnings = report.get("warnings", [])
        failures = report.get("failures", [])
        if failures:
            print(f"\n  失败 ({len(failures)}):")
            for iss in failures:
                print(f"    ✗ {iss}")
        if warnings:
            print(f"\n  警告 ({len(warnings)}):")
            for iss in warnings:
                print(f"    ⚠ {iss}")
        if not warnings and not failures:
            empty_hints = report.get("empty_hints", [])
            if empty_hints:
                print(f"\n  💡 提示:")
                for hint in empty_hints:
                    print(f"    · {hint}")
            else:
                print("\n  未发现问题。")
        print()
        return 0 if status == "OK" else (1 if status == "FAIL" else 0)

    else:
        print("Usage: python novel.py story {init|contract|commit|health}")
        return 1


def cmd_query(args):
    """Query project memory for matching content."""
    if not _story_exists():
        print(f"  {_story_missing_msg()}")
        return 1

    question = " ".join(getattr(args, "question", []) or [])
    if not question.strip():
        print("Usage: python novel.py query <question>")
        print("Example: python novel.py query 主角的名字是什么")
        return 1

    print(f"  查询: {question}")
    print()

    story = PROJECT_ROOT / ".story"

    # Search memory JSON files
    memory = story / "memory"
    hits = 0

    for fname, label in [("characters.json", "角色"), ("promises.json", "伏笔"),
                          ("world_facts.json", "世界观"), ("learned_rules.json", "规则")]:
        fp = memory / fname
        if not fp.exists():
            continue
        try:
            import json as _json
            data = _json.loads(fp.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for item in data:
                    text = str(item)
                    if question.lower() in text.lower() or any(kw in text for kw in question.split()):
                        hits += 1
                        preview = text[:120].replace("\n", " ")
                        print(f"  [{label}] {preview}...")
        except Exception:
            pass

    # Search event ledger
    ledger = story / "events" / "event_ledger.jsonl"
    if ledger.exists():
        try:
            for line in ledger.read_text(encoding="utf-8").strip().split("\n"):
                if not line.strip():
                    continue
                if question.lower() in line.lower() or any(kw in line for kw in question.split()):
                    hits += 1
                    import json as _json
                    evt = _json.loads(line)
                    preview = str(evt.get("event", line))[:120]
                    print(f"  [事件 ch{evt.get('chapter', '?')}] {preview}...")
        except Exception:
            pass

    # Search contracts
    chapters_dir = story / "chapters"
    if chapters_dir.exists():
        for cf in sorted(chapters_dir.glob("chapter_*_contract.json")):
            try:
                import json as _json
                text = cf.read_text(encoding="utf-8")
                if question.lower() in text.lower() or any(kw in text for kw in question.split()):
                    hits += 1
                    data = _json.loads(text)
                    ch_no = data.get('chapter_no', '?')
                    ch_title = data.get('chapter_title', '')
                    scene_goal = data.get('required_scene_goal', '')
                    open_promises = data.get('open_promises_to_keep', [])
                    forbidden = data.get('forbidden_changes', [])
                    active_chars = data.get('active_characters', [])
                    min_rules = data.get('minimum_quality_rules', {})
                    must_advance = min_rules.get('must_advance_plot', None)
                    print(f"  [合同 ch{ch_no}] {ch_title}")
                    if scene_goal:
                        print(f"    场景目标: {scene_goal}")
                    if open_promises:
                        print(f"    开放伏笔 ({len(open_promises)}):")
                        for p in open_promises[:3]:
                            print(f"      · {str(p)[:80]}")
                        if len(open_promises) > 3:
                            print(f"      ...还有 {len(open_promises)-3} 个")
                    if forbidden:
                        print(f"    禁止变更 ({len(forbidden)}):")
                        for f in forbidden[:3]:
                            print(f"      · {str(f)[:80]}")
                        if len(forbidden) > 3:
                            print(f"      ...还有 {len(forbidden)-3} 项")
                    if must_advance is not None:
                        print(f"    必须推进剧情: {'是' if must_advance else '否'}")
                    if active_chars:
                        print(f"    活跃角色: {len(active_chars)} 个")
            except Exception:
                pass

    if hits == 0:
        print("  未找到匹配的记忆。")
    else:
        print(f"\n  共 {hits} 条匹配。")
    return 0


def cmd_learn(args):
    """Add/list/remove learned writing rules."""
    if not _story_exists():
        print(f"  {_story_missing_msg()}")
        return 1

    import json as _json

    rules_file = PROJECT_ROOT / ".story" / "memory" / "learned_rules.json"
    rules = []
    if rules_file.exists():
        try:
            rules = _json.loads(rules_file.read_text(encoding="utf-8"))
        except Exception:
            rules = []

    action = getattr(args, "action", "list")
    rule_text = " ".join(getattr(args, "rule", []) or [])

    # Auto-detect: if action is not a known command, treat it as rule text
    if action not in ("add", "list", "remove"):
        rule_text = action + (" " + rule_text if rule_text else "")
        action = "add"

    if action == "list":
        if not rules:
            print("  暂无已学规则。用 python novel.py learn add <规则> 添加。")
            return 0
        print(f"  已学规则 ({len(rules)}):")
        for i, r in enumerate(rules):
            rule_str = r.get("rule", str(r))
            ch = r.get("chapter", "?")
            print(f"    [{i+1}] (ch{ch}) {rule_str}")
        return 0

    elif action == "add":
        if not rule_text.strip():
            print("Usage: python novel.py learn add <规则内容>")
            print("Example: python novel.py learn add 主角李明的口头禅是'走着瞧'")
            return 1
        from datetime import datetime
        rules.append({
            "rule": rule_text,
            "chapter": "manual",
            "added_at": datetime.now().isoformat(),
        })
        rules_file.write_text(_json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] 规则已添加: {rule_text}")
        return 0

    elif action == "remove":
        if not rule_text.strip():
            print("Usage: python novel.py learn remove <number>")
            return 1
        try:
            idx = int(rule_text) - 1
            if 0 <= idx < len(rules):
                removed = rules.pop(idx)
                rules_file.write_text(_json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"  [OK] 规则已移除: {removed.get('rule', str(removed))}")
                return 0
            else:
                print(f"  无效编号: {idx+1} (共 {len(rules)} 条)")
                return 1
        except ValueError:
            print(f"  请输入有效编号。当前共 {len(rules)} 条规则。")
            return 1

    return 0


def cmd_board(args):
    """Print a readonly status board for the project."""
    print("=" * 60)
    print("  Novel Pipeline — 项目看板")
    print("=" * 60)
    print()

    # Version
    v = get_version()
    print(f"  引擎版本: {v}")

    # Story status
    if _story_exists():
        from scripts.story import story_health
        health = story_health.check_health(PROJECT_ROOT)
        status = health["status"]
        print(f"  故事链: {status}")
        print(f"    合同: {health.get('contract_count', 0)}  提交: {health.get('commit_count', 0)}  事件: {health.get('event_count', 0)}")
        issues = health.get("issues", [])
        if issues:
            for iss in issues[:3]:
                print(f"    ⚠ {iss}")
    else:
        print(f"  故事链: 未初始化 (python novel.py story init)")

    # Config
    cfg = PROJECT_ROOT / "config.json"
    if cfg.exists():
        import json as _json
        try:
            cfg_data = _load_project_config()
            slug = cfg_data.get("default_novel_slug", "?")
            genre = cfg_data.get("default_genre", "?")
            style = cfg_data.get("default_style", "?")
            print(f"  当前项目: {slug}")
            print(f"  类型/风格: {genre} / {style}")

            # Word count config
            wc = cfg_data.get("word_count", {}).get("normal", {})
            if wc:
                print(f"  字数范围: {wc.get('min', '?')}-{wc.get('max', '?')} (最佳≥{wc.get('best_min', '?')})")
        except Exception:
            print(f"  配置: 读取失败")
    else:
        print(f"  配置: 未找到 config.json")

    # Chapters in novels dir
    if cfg.exists():
        import json as _json
        try:
            cfg_data = _load_project_config()
            slug = cfg_data.get("default_novel_slug", "demo_novel")
            novels_root = resolve_path(PROJECT_ROOT, cfg_data.get("novels_root", "./novels"))
            ch_dir = Path(novels_root) / slug / "第01卷"
            if ch_dir.exists():
                chapters = sorted(ch_dir.glob("第*章*.txt"))
                print(f"  已完成章节: {len(chapters)}")
                if chapters:
                    latest = chapters[-1]
                    cn = sum(1 for c in latest.read_text(encoding="utf-8")
                             if '\u4e00' <= c <= '\u9fff' or '\u3400' <= c <= '\u4dbf')
                    print(f"    最新: {latest.name} ({cn} 汉字)")
            else:
                print(f"  章节目录: 未找到 {ch_dir}")
        except Exception:
            print(f"  章节: 读取失败")

    # DB status
    try:
        # P0-2: Use active slot novel.db instead of config.json db_path
        dbp = _get_active_db_path()
        if dbp.exists():
            import sqlite3
            conn = sqlite3.connect(str(dbp))
            cur = conn.execute("SELECT COUNT(*) FROM chapters")
            ch_count = cur.fetchone()[0]
            cur = conn.execute("SELECT COUNT(*) FROM characters")
            char_count = cur.fetchone()[0]
            conn.close()
            print(f"  数据库: {dbp.name} | 章节: {ch_count} | 角色: {char_count}")
        else:
            print(f"  数据库: 未找到 ({dbp})")
    except Exception:
        print(f"  数据库: 无法读取")

    print()
    print("=" * 60)
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


def cmd_db(args):
    """Multi-DB workspace management commands."""
    action = getattr(args, "db_action", None)

    if action == "init":
        return _db_init(getattr(args, "force", False))
    elif action == "list":
        return _db_list()
    elif action == "current":
        return _db_current()
    elif action == "info":
        return _db_info()
    elif action == "new":
        return _db_new(getattr(args, "name", ""), getattr(args, "description", ""))
    elif action == "use":
        return _db_use(getattr(args, "slot_id", ""))
    elif action == "delete":
        return _db_delete(
            getattr(args, "slot_id", ""),
            yes=getattr(args, "yes", False),
        )
    elif action == "trash":
        return _db_trash()
    elif action == "restore":
        return _db_restore(
            getattr(args, "slot_id", ""),
            backup_id=getattr(args, "backup_id", None),
            from_trash=getattr(args, "from_trash", False),
        )
    elif action == "purge":
        return _db_purge(getattr(args, "trash_name", None))
    elif action == "backup":
        return _db_backup(getattr(args, "slot", None))
    else:
        print("用法: python novel.py db {init|list|current|info|new|use|delete|trash|restore|purge|backup}")
        print()
        print("  init         初始化 workspace 目录结构")
        print("  list         列出所有 DB slot")
        print("  current      显示当前活跃 DB slot")
        print("  info         显示当前 slot 详细信息")
        print("  new          创建新 DB slot (--name <名称>)")
        print("  use          切换到指定 DB slot")
        print("  delete       安全删除 DB slot (移至回收站, --yes 确认)")
        print("  trash        查看回收站中的 slot")
        print("  restore      从备份恢复 DB slot (--from-trash 从回收站恢复)")
        print("  purge        永久删除回收站中的 slot")
        print("  backup       备份当前 DB slot")
        return 1


def _get_workspace_dir() -> Path:
    """Get workspace directory path."""
    return PROJECT_ROOT / "workspace"


def _get_active_db_path() -> Path:
    """Get the novel.db path for the currently active slot.

    Priority:
    1. workspace/registry.json → active_slot → workspace/<slot>/novel.db
    2. Fallback: config.json db_path (legacy global DB)
    """
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if registry_file.exists():
        try:
            registry = _json.loads(registry_file.read_text(encoding="utf-8"))
            active = registry.get("active_slot", "")
            if active:
                slot_db = ws_dir / active / "novel.db"
                if slot_db.exists():
                    return slot_db
        except Exception:
            pass

    # Fallback: legacy config.json db_path
    try:
        cfg_data = _load_project_config()
        db = cfg_data.get("db_path", "./data/novel_memory.db")
        p = Path(db)
        if not p.is_absolute():
            p = PROJECT_ROOT / db
        return p
    except Exception:
        return PROJECT_ROOT / "data" / "novel_memory.db"


def _db_init(force=False):
    """Initialize workspace directory structure."""
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if registry_file.exists() and not force:
        print("  workspace/ 已经初始化。")
        print("  使用 --force 强制重新初始化。")
        return 0

    import json as _json
    from datetime import datetime

    # Create workspace directory
    ws_dir.mkdir(parents=True, exist_ok=True)

    # Create initial registry
    registry = {
        "version": "1.0",
        "created_at": datetime.now().isoformat(),
        "active_slot": "slot_001",
        "slots": [
            {
                "id": "slot_001",
                "name": "默认工作区",
                "description": "默认项目工作区",
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "project_count": 0,
            }
        ],
    }
    registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  [OK] workspace/registry.json 已创建")

    # Create 3 initial slots
    for i in range(1, 4):
        slot_id = f"slot_{i:03d}"
        slot_dir = ws_dir / slot_id
        _create_slot_structure(slot_dir)
        print(f"  [OK] {slot_id}/ 目录已创建")

    # P0-5: Register all 3 slots in registry (not just slot_001)
    if len(registry["slots"]) < 3:
        registry["slots"].append({
            "id": "slot_002", "name": "空闲工作区 2",
            "description": "空闲工作区", "status": "normal",
            "created_at": datetime.now().isoformat(), "project_count": 0,
        })
        registry["slots"].append({
            "id": "slot_003", "name": "空闲工作区 3",
            "description": "空闲工作区", "status": "normal",
            "created_at": datetime.now().isoformat(), "project_count": 0,
        })
        registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    # P0-1 clean3: Migrate all existing slot DBs to include FTS5 tables
    for i in range(1, 4):
        slot_id = f"slot_{i:03d}"
        slot_dir = ws_dir / slot_id
        if slot_dir.exists():
            _migrate_slot_fts(slot_dir)

    print()
    print("  workspace 初始化完成！")
    print(f"  活跃 slot: slot_001")
    print(f"  使用 python novel.py db new --name <名称> 创建更多工作区")
    return 0


def _create_slot_structure(slot_dir: Path):
    """Create standard slot directory structure including novel.db."""
    import json as _json
    import sqlite3
    from datetime import datetime

    slot_dir.mkdir(parents=True, exist_ok=True)
    for subdir in ["outlines", "chapters", "reports", "exports", "backups"]:
        (slot_dir / subdir).mkdir(parents=True, exist_ok=True)

    # P0-2: Create per-slot novel.db with full schema (if not exists)
    db_path = slot_dir / "novel.db"
    if not db_path.exists():
        conn = sqlite3.connect(str(db_path))
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS novels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    genre TEXT DEFAULT '',
                    theme TEXT DEFAULT '',
                    description TEXT DEFAULT '',
                    target_words INTEGER DEFAULT 0,
                    current_words INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'planning',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT DEFAULT 'note',
                    project TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT DEFAULT '',
                    importance INTEGER DEFAULT 3,
                    source TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    last_used_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS volumes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    title TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    target_words INTEGER DEFAULT 0,
                    UNIQUE(novel_id, volume_no)
                );

                CREATE TABLE IF NOT EXISTS chapters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_id INTEGER REFERENCES volumes(id),
                    chapter_no INTEGER NOT NULL,
                    title TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    summary TEXT DEFAULT '',
                    word_count INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'draft',
                    file_path TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, chapter_no)
                );

                CREATE TABLE IF NOT EXISTS chapter_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    chunk_no INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS characters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    name TEXT NOT NULL,
                    alias TEXT DEFAULT '',
                    role TEXT DEFAULT '',
                    identity TEXT DEFAULT '',
                    personality TEXT DEFAULT '',
                    motivation TEXT DEFAULT '',
                    ability TEXT DEFAULT '',
                    relationship TEXT DEFAULT '',
                    arc TEXT DEFAULT '',
                    status TEXT DEFAULT 'active',
                    tags TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS worldbuilding (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    category TEXT DEFAULT '',
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    importance INTEGER DEFAULT 3,
                    tags TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS plot_threads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    thread_type TEXT DEFAULT '伏笔',
                    introduced_chapter INTEGER,
                    resolved_chapter INTEGER,
                    status TEXT DEFAULT 'open',
                    importance INTEGER DEFAULT 3
                );

                CREATE TABLE IF NOT EXISTS writing_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    title TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    rule_type TEXT DEFAULT 'other',
                    importance INTEGER DEFAULT 3,
                    status TEXT DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS chapter_summaries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    short_summary TEXT DEFAULT '',
                    long_summary TEXT DEFAULT '',
                    key_events TEXT DEFAULT '',
                    characters_involved TEXT DEFAULT '',
                    new_settings TEXT DEFAULT '',
                    foreshadowing TEXT DEFAULT '',
                    continuity_notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, chapter_id)
                );

                CREATE TABLE IF NOT EXISTS continuity_checks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER NOT NULL REFERENCES chapters(id),
                    check_type TEXT DEFAULT 'continuity',
                    issue TEXT DEFAULT '',
                    suggestion TEXT DEFAULT '',
                    severity INTEGER DEFAULT 1,
                    status TEXT DEFAULT 'open',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS novel_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT NOT NULL,
                    target_type TEXT,
                    target_id INTEGER,
                    detail TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS chapter_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    chapter_id INTEGER,
                    chapter_no INTEGER NOT NULL,
                    version_no INTEGER NOT NULL DEFAULT 1,
                    version_status TEXT DEFAULT 'draft',
                    title TEXT DEFAULT '',
                    content TEXT NOT NULL,
                    word_count INTEGER DEFAULT 0,
                    change_reason TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS reader_promises (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    promise_title TEXT NOT NULL,
                    promise_detail TEXT NOT NULL,
                    introduced_chapter INTEGER,
                    expected_payoff_range TEXT DEFAULT '',
                    payoff_chapter INTEGER,
                    status TEXT DEFAULT 'open',
                    importance INTEGER DEFAULT 3,
                    reader_emotion TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS volume_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    planned_title TEXT DEFAULT '',
                    final_title TEXT DEFAULT '',
                    title_status TEXT DEFAULT 'planned',
                    suggested_chapters INTEGER DEFAULT 25,
                    min_chapters INTEGER DEFAULT 20,
                    max_chapters INTEGER DEFAULT 29,
                    volume_goal TEXT DEFAULT '',
                    opening_state TEXT DEFAULT '',
                    ending_target TEXT DEFAULT '',
                    must_complete TEXT DEFAULT '',
                    unresolved_hooks_to_next TEXT DEFAULT '',
                    outline_version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, volume_no)
                );

                CREATE TABLE IF NOT EXISTS chapter_plans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER NOT NULL,
                    chapter_no INTEGER NOT NULL,
                    planned_title TEXT DEFAULT '',
                    final_title TEXT DEFAULT '',
                    title_status TEXT DEFAULT 'planned',
                    plan_status TEXT DEFAULT 'planned',
                    chapter_goal TEXT DEFAULT '',
                    main_event TEXT DEFAULT '',
                    character_focus TEXT DEFAULT '',
                    conflict_point TEXT DEFAULT '',
                    must_include TEXT DEFAULT '',
                    plot_threads_to_advance TEXT DEFAULT '',
                    reader_promises_to_advance TEXT DEFAULT '',
                    ending_hook_direction TEXT DEFAULT '',
                    continuity_from_previous TEXT DEFAULT '',
                    title_change_reason TEXT DEFAULT '',
                    actual_word_count INTEGER DEFAULT 0,
                    actual_summary TEXT DEFAULT '',
                    completion_status TEXT DEFAULT '',
                    ingested_at TEXT DEFAULT '',
                    outline_version INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT (datetime('now')),
                    updated_at TEXT DEFAULT (datetime('now')),
                    UNIQUE(novel_id, volume_no, chapter_no)
                );

                CREATE TABLE IF NOT EXISTS title_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    novel_id INTEGER NOT NULL REFERENCES novels(id),
                    volume_no INTEGER,
                    chapter_no INTEGER,
                    old_title TEXT DEFAULT '',
                    new_title TEXT DEFAULT '',
                    title_type TEXT DEFAULT 'chapter',
                    change_reason TEXT DEFAULT '',
                    changed_at TEXT DEFAULT (datetime('now'))
                );

                -- FTS5 全文检索索引 (v0.6.5-clean3)
                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
                    title, content, summary,
                    content='chapters', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
                    content, summary,
                    content='chapter_chunks', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_character_fts USING fts5(
                    name, alias, identity, personality, tags,
                    content='characters', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_world_fts USING fts5(
                    title, content, tags,
                    content='worldbuilding', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS novel_plot_fts USING fts5(
                    title, content,
                    content='plot_threads', content_rowid='id'
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    title, content, tags,
                    content='memories', content_rowid='id'
                );
            """)
            conn.commit()
        finally:
            conn.close()

    # Create project.json if not exists
    proj_file = slot_dir / "project.json"
    if not proj_file.exists():
        proj_file.write_text(_json.dumps({
            "name": slot_dir.name,
            "title": "未命名项目",
            "active_outline": None,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")


def _migrate_slot_fts(slot_dir: Path) -> bool:
    """Ensure a slot's novel.db has FTS5 tables (idempotent migration)."""
    import sqlite3
    db_path = slot_dir / "novel.db"
    if not db_path.exists():
        return False
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript("""
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_chapter_fts USING fts5(
                title, content, summary,
                content='chapters', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_chunk_fts USING fts5(
                content, summary,
                content='chapter_chunks', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_character_fts USING fts5(
                name, alias, identity, personality, tags,
                content='characters', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_world_fts USING fts5(
                title, content, tags,
                content='worldbuilding', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS novel_plot_fts USING fts5(
                title, content,
                content='plot_threads', content_rowid='id'
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                title, content, tags,
                content='memories', content_rowid='id'
            );
        """)
        conn.commit()
        return True
    finally:
        conn.close()


def _db_list():
    """List all DB slots with detailed info."""
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = registry.get("active_slot", "")
    slots = registry.get("slots", [])

    print("=" * 70)
    print("  作品列表")
    print("=" * 70)
    print()

    if not slots:
        print("  暂无作品。用「创建一本新小说的工作区」来添加第一本吧！")
        return 0

    for s in slots:
        sid = s.get("id", "?")
        name = s.get("name", "")
        status = s.get("status", "?")
        desc = s.get("description", "")
        is_active = (sid == active)

        # ── 读取 slot 目录下的详细信息 ──
        slot_dir = ws_dir / sid
        outline_title = ""
        outline_count = 0
        chapter_count = 0
        word_count = 0

        if slot_dir.exists():
            # 统计大纲
            outlines_dir = slot_dir / "outlines"
            if outlines_dir.exists():
                outline_files = list(outlines_dir.glob("*.json"))
                outline_count = len(outline_files)

            # 读取 project.json 获取活跃大纲标题
            proj_file = slot_dir / "project.json"
            if proj_file.exists():
                try:
                    proj = _json.loads(proj_file.read_text(encoding="utf-8"))
                    active_oid = proj.get("active_outline", "")
                    if active_oid:
                        o_file = outlines_dir / f"{active_oid}.json" if outlines_dir.exists() else None
                        if o_file and o_file.exists():
                            o_data = _json.loads(o_file.read_text(encoding="utf-8"))
                            outline_title = o_data.get("title", "")
                            chapter_count = o_data.get("chapter_count", 0)
                except Exception:
                    pass

            # P1-5: 从 novel.db 统计章节和字数（真实数据）
            db_file = slot_dir / "novel.db"
            if db_file.exists():
                try:
                    import sqlite3
                    conn = sqlite3.connect(str(db_file))
                    cur = conn.execute("SELECT COUNT(*), COALESCE(SUM(word_count), 0) FROM chapters")
                    row = cur.fetchone()
                    if row:
                        db_ch_count, db_wc = row
                        chapter_count = max(chapter_count, db_ch_count or 0)
                        word_count = db_wc or 0
                    conn.close()
                except Exception:
                    pass

        # ── 显示 ──
        marker = "★" if is_active else " "
        status_cn = "当前使用中" if is_active else ("正常" if status == "active" else status)

        print(f"  {marker} [{sid}] {name}")
        print(f"      状态: {status_cn}")
        if outline_title:
            print(f"      大纲: {outline_title}")
        print(f"      大纲版本数: {outline_count}  |  章节数: {chapter_count}  |  总字数: {word_count:,}")
        if desc:
            print(f"      描述: {desc}")
        print()

    print(f"  共 {len(slots)} 个作品，当前正在写: {active}")
    return 0


def _db_current():
    """Show current active DB slot."""
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = registry.get("active_slot", "")

    if not active:
        print("  当前无活跃 slot。运行 python novel.py db use <slot_id>")
        return 0

    # Find slot info
    slot_info = None
    for s in registry.get("slots", []):
        if s.get("id") == active:
            slot_info = s
            break

    print(f"  当前活跃 DB slot: {active}")
    if slot_info:
        print(f"  名称: {slot_info.get('name', '')}")
        desc = slot_info.get("description", "")
        if desc:
            print(f"  描述: {desc}")
        print(f"  项目数: {slot_info.get('project_count', 0)}")
    return 0


def _db_info():
    """Show detailed info about current slot."""
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = registry.get("active_slot", "")
    slot_dir = ws_dir / active

    print("=" * 60)
    print(f"  DB Slot 详细信息: {active}")
    print("=" * 60)
    print()

    # Registry info
    slot_info = None
    for s in registry.get("slots", []):
        if s.get("id") == active:
            slot_info = s
            break

    if slot_info:
        print(f"  名称: {slot_info.get('name', '')}")
        print(f"  描述: {slot_info.get('description', '(无)')}")
        print(f"  状态: {slot_info.get('status', '?')}")
        print(f"  创建时间: {slot_info.get('created_at', '?')}")
        print(f"  项目数: {slot_info.get('project_count', 0)}")
    print()

    # Directory structure
    print(f"  目录: {slot_dir}")
    if slot_dir.exists():
        print("  子目录:")
        for subdir in ["outlines", "chapters", "reports", "exports", "backups"]:
            exists = (slot_dir / subdir).exists()
            mark = "✓" if exists else "✗"
            count = len(list((slot_dir / subdir).iterdir())) if exists else 0
            print(f"    {mark} {subdir}/ ({count} 项)")
    else:
        print("  ⚠️  目录不存在！")

    # project.json
    proj_file = slot_dir / "project.json"
    if proj_file.exists():
        proj = _json.loads(proj_file.read_text(encoding="utf-8"))
        print()
        print("  项目信息:")
        print(f"    名称: {proj.get('title', proj.get('name', '?'))}")
        print(f"    活跃大纲: {proj.get('active_outline', '(未设定)')}")
        print(f"    最后更新: {proj.get('updated_at', '?')}")
    print()
    return 0


def _db_new(name, description=""):
    """Create a new DB slot."""
    import json as _json
    from datetime import datetime
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    slots = registry.get("slots", [])

    # Auto-generate slot ID
    max_idx = 0
    for s in slots:
        sid = s.get("id", "")
        if sid.startswith("slot_"):
            try:
                idx = int(sid.replace("slot_", ""))
                if idx > max_idx:
                    max_idx = idx
            except ValueError:
                pass

    next_idx = max_idx + 1
    slot_id = f"slot_{next_idx:03d}"

    # Check if we need to auto-create more slots
    if max_idx >= 3 and (max_idx + 1) % 4 == 0:
        print(f"  ℹ️  已满 {max_idx} 个 slot，正在创建 {slot_id}（将自动扩展后续 slot）。")

    # Create slot structure
    slot_dir = ws_dir / slot_id
    _create_slot_structure(slot_dir)

    # Update project.json with name
    proj_file = slot_dir / "project.json"
    proj = _json.loads(proj_file.read_text(encoding="utf-8"))
    proj["name"] = name
    proj["title"] = name
    proj["updated_at"] = datetime.now().isoformat()
    proj_file.write_text(_json.dumps(proj, ensure_ascii=False, indent=2), encoding="utf-8")

    # Add to registry
    new_slot = {
        "id": slot_id,
        "name": name,
        "description": description,
        "status": "active",
        "created_at": datetime.now().isoformat(),
        "project_count": 1,
    }
    slots.append(new_slot)
    registry["slots"] = slots
    registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✅ 新 DB slot 创建成功！")
    print(f"  Slot ID: {slot_id}")
    print(f"  名称: {name}")
    if description:
        print(f"  描述: {description}")
    print(f"  目录: {slot_dir}")
    print()
    print(f"  使用 python novel.py db use {slot_id} 切换到此工作区")
    return 0


def _db_use(slot_id):
    """Switch to a different DB slot."""
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))

    # Verify slot exists
    slot_dir = ws_dir / slot_id
    if not slot_dir.exists():
        print(f"  ❌ Slot {slot_id} 不存在。")
        slots = [s.get("id") for s in registry.get("slots", [])]
        if slots:
            print(f"  可用 slot: {', '.join(slots)}")
        return 1

    # Verify in registry
    found = False
    for s in registry.get("slots", []):
        if s.get("id") == slot_id:
            found = True
            break
    if not found:
        print(f"  ⚠️  {slot_id} 目录存在但未在注册表中。正在添加...")
        from datetime import datetime
        registry["slots"].append({
            "id": slot_id,
            "name": slot_id,
            "description": "",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "project_count": 0,
        })

    old_active = registry.get("active_slot", "")
    registry["active_slot"] = slot_id
    registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✅ 已切换到 {slot_id}")
    if old_active and old_active != slot_id:
        print(f"  (之前: {old_active})")

    # Show slot info
    proj_file = slot_dir / "project.json"
    if proj_file.exists():
        proj = _json.loads(proj_file.read_text(encoding="utf-8"))
        print(f"  项目: {proj.get('title', proj.get('name', '?'))}")
        outline = proj.get("active_outline", "")
        if outline:
            print(f"  大纲: {outline}")
    return 0


def _db_delete(slot_id, yes=False):
    """Safe delete a DB slot — moves to workspace/_trash/ by default.

    With --yes flag, performs safe delete (move to trash).
    Without --yes, prompts for confirmation.
    """
    import json as _json
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = registry.get("active_slot", "")

    if slot_id == active:
        print(f"  ❌ 不能删除当前活跃的 slot ({slot_id})。")
        print(f"  请先切换到其他 slot: python novel.py db use <other>")
        return 1

    if slot_id == "slot_001":
        print(f"  ⚠️  slot_001 是默认工作区，不能删除。")
        return 1

    # Verify slot exists
    if not any(s.get("id") == slot_id for s in registry.get("slots", [])):
        print(f"  ❌ Slot {slot_id} 不在注册表中。")
        return 1

    # Require confirmation
    if not yes:
        print(f"  ⚠️  即将安全删除 slot {slot_id}（移至回收站）。")
        print(f"  使用 --yes 确认删除。")
        print(f"  查看回收站: python novel.py db trash")
        return 1

    # Use SlotManager for safe trash-based deletion
    try:
        from scripts.db.slot_manager import SlotManager
        mgr = SlotManager(PROJECT_ROOT)
        result = mgr.delete_slot_safe(slot_id, confirm=True)

        if result["status"] == "ok":
            print(f"  ✅ {result['message']}")
            print(f"  回收站标识: {result.get('trash_name', '?')}")
            remaining = len(registry.get("slots", [])) - 1
            print(f"  剩余 slot: {remaining} 个")
            print()
            print(f"  提示: 使用 python novel.py db trash 查看回收站")
            print(f"       使用 python novel.py db restore --from-trash {result.get('trash_name', '')} 恢复")
            print(f"       使用 python novel.py db purge {result.get('trash_name', '')} 永久删除")
            return 0
        else:
            print(f"  ❌ 删除失败: {result.get('message', '未知错误')}")
            return 1
    except ImportError:
        # Fallback: old-style permanent delete with confirmation
        print(f"  ⚠️  SlotManager 不可用，回退到永久删除模式。")
        print(f"  确认永久删除 {slot_id} 吗？此操作不可逆！")
        print(f"  使用 --yes 确认。")
        return 1


def _db_restore(slot_id, backup_id=None, from_trash=False):
    """Restore a DB slot from backup or from trash.

    With --from-trash: restore from workspace/_trash/ (trash_name format).
    Without --from-trash: restore from slot's backup directory (existing behavior).
    """
    if from_trash:
        return _db_restore_from_trash(slot_id)

    import json as _json
    from datetime import datetime
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    slot_dir = ws_dir / slot_id
    backup_dir = slot_dir / "backups"

    if not backup_dir.exists():
        print(f"  ❌ {slot_id} 没有备份目录。")
        return 1

    # Find backups
    backups = sorted(backup_dir.glob("*.json"), reverse=True)
    if not backups:
        print(f"  ❌ {slot_id} 没有可用的备份文件。")
        return 1

    target = None
    if backup_id:
        for b in backups:
            if backup_id in b.name:
                target = b
                break
        if not target:
            print(f"  ❌ 未找到备份 {backup_id}")
            print(f"  可用备份: {', '.join(b.name for b in backups)}")
            return 1
    else:
        target = backups[0]  # Latest

    print(f"  从备份恢复: {target.name}")
    print(f"  备份时间: {datetime.fromtimestamp(target.stat().st_mtime).strftime('%Y-%m-%d %H:%M')}")

    # Restore project.json from backup
    try:
        backup_data = _json.loads(target.read_text(encoding="utf-8"))
        proj_file = slot_dir / "project.json"
        proj_file.write_text(_json.dumps(backup_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ project.json 已从备份恢复。")

        # Also update registry
        registry = _json.loads(registry_file.read_text(encoding="utf-8"))
        for s in registry.get("slots", []):
            if s.get("id") == slot_id:
                s["status"] = "active"
                s["name"] = backup_data.get("name", backup_data.get("title", s.get("name", slot_id)))
                break
        registry_file.write_text(_json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✅ 注册表已更新。")
    except Exception as e:
        print(f"  ❌ 恢复失败: {e}")
        return 1

    return 0


def _db_backup(slot=None):
    """Backup the current DB slot's project.json."""
    import json as _json
    from datetime import datetime
    ws_dir = _get_workspace_dir()
    registry_file = ws_dir / "registry.json"

    if not registry_file.exists():
        print("  workspace/ 未初始化。运行 python novel.py db init")
        return 1

    registry = _json.loads(registry_file.read_text(encoding="utf-8"))
    active = slot or registry.get("active_slot", "")

    if not active:
        print("  ❌ 无活跃 slot。请指定 --slot <id> 或先切换。")
        return 1

    slot_dir = ws_dir / active
    proj_file = slot_dir / "project.json"
    backup_dir = slot_dir / "backups"

    if not proj_file.exists():
        print(f"  ⚠️  {active}/project.json 不存在，创建模板...")
        _create_slot_structure(slot_dir)

    backup_dir.mkdir(parents=True, exist_ok=True)

    # Read current project.json
    proj = _json.loads(proj_file.read_text(encoding="utf-8"))
    proj["backed_up_at"] = datetime.now().isoformat()

    # Create backup file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"backup_{timestamp}.json"
    backup_file.write_text(_json.dumps(proj, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"  ✅ 备份完成！")
    print(f"  Slot: {active}")
    print(f"  备份文件: backup_{timestamp}.json")
    print(f"  位置: {backup_file}")
    return 0


# === P1-3: Trash management CLI helpers ===

def _db_trash():
    """List items in workspace/_trash/."""
    ws_dir = _get_workspace_dir()
    trash_dir = ws_dir / "_trash"

    if not trash_dir.exists():
        print("  回收站为空。")
        return 0

    try:
        from scripts.db.slot_manager import SlotManager
        mgr = SlotManager(PROJECT_ROOT)
        items = mgr.list_trash()
    except ImportError:
        items = []
        for entry in sorted(trash_dir.iterdir(), key=lambda p: p.name, reverse=True):
            if entry.is_dir():
                size = sum(f.stat().st_size for f in entry.rglob("*") if f.is_file())
                items.append({
                    "trash_name": entry.name,
                    "original_slot_id": entry.name.split("_", 2)[-1] if "_" in entry.name else entry.name,
                    "trashed_at": "",
                    "size_bytes": size,
                })

    if not items:
        print("  回收站为空。")
        return 0

    print("=" * 60)
    print("  回收站 (workspace/_trash/)")
    print("=" * 60)
    print()

    for item in items:
        trash_name = item.get("trash_name", "?")
        original = item.get("original_slot_id", "?")
        trashed_at = item.get("trashed_at", "")
        size = item.get("size_bytes", 0)

        if trashed_at:
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(trashed_at)
                trashed_at = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                pass

        size_str = f"{size:,}B" if size < 1024 else f"{size/1024:.1f}KB" if size < 1024*1024 else f"{size/(1024*1024):.1f}MB"
        print(f"  🗑️  {trash_name}")
        print(f"     原始 Slot: {original}")
        if trashed_at:
            print(f"     删除时间: {trashed_at}")
        print(f"     大小: {size_str}")
        print()

    print(f"  共 {len(items)} 项")
    print()
    print(f"  恢复: python novel.py db restore --from-trash <trash_name>")
    print(f"  永久删除: python novel.py db purge <trash_name>")
    print(f"  清空回收站: python novel.py db purge")
    return 0


def _db_restore_from_trash(trash_name):
    """Restore a slot from workspace/_trash/."""
    if not trash_name:
        print("  ❌ 请指定回收站中的项目名。")
        print("  使用 python novel.py db trash 查看回收站。")
        return 1

    try:
        from scripts.db.slot_manager import SlotManager
        mgr = SlotManager(PROJECT_ROOT)
        result = mgr.restore_slot_from_trash(trash_name)

        if result["status"] == "ok":
            print(f"  ✅ {result['message']}")
            print(f"  Slot ID: {result.get('slot_id', '?')}")
            print()
            print(f"  切换到恢复的 slot: python novel.py db use {result.get('slot_id', '')}")
            return 0
        else:
            print(f"  ❌ 恢复失败: {result.get('message', '未知错误')}")
            available = result.get("available", [])
            if available:
                print(f"  回收站中可用的项目: {', '.join(available)}")
            return 1
    except ImportError:
        # Fallback: manual restore
        ws_dir = _get_workspace_dir()
        trash_dir = ws_dir / "_trash"
        source = trash_dir / trash_name

        if not source.exists():
            print(f"  ❌ 回收站中未找到: {trash_name}")
            return 1

        # Try to determine original slot ID
        parts = trash_name.split("_", 2)
        slot_id = parts[2] if len(parts) >= 3 else trash_name
        target = ws_dir / slot_id

        if target.exists():
            print(f"  ❌ Slot {slot_id} 已存在于 workspace 中。")
            return 1

        import shutil
        shutil.move(str(source), str(target))
        print(f"  ✅ 已恢复 {slot_id} (手动模式)")
        print(f"  请运行 python novel.py db init --force 重建注册表。")
        return 0


def _db_purge(trash_name=None):
    """Permanently delete items from workspace/_trash/."""
    try:
        from scripts.db.slot_manager import SlotManager
        mgr = SlotManager(PROJECT_ROOT)
        result = mgr.purge_trash(trash_name)

        if result["status"] == "ok":
            if trash_name:
                print(f"  ✅ {result['message']}")
            else:
                purged = result.get("purged", [])
                if not purged:
                    print("  回收站为空，无需清空。")
                else:
                    print(f"  ✅ 已永久删除 {len(purged)} 项:")
                    for name in purged:
                        print(f"     - {name}")
            return 0
        elif result["status"] == "partial":
            print(f"  ⚠️  {result['message']}")
            for err in result.get("errors", []):
                print(f"     ❌ {err['item']}: {err['error']}")
            return 1
        else:
            print(f"  ❌ {result.get('message', '未知错误')}")
            return 1
    except ImportError:
        # Fallback: manual purge
        import shutil
        ws_dir = _get_workspace_dir()
        trash_dir = ws_dir / "_trash"

        if not trash_dir.exists():
            print("  回收站为空。")
            return 0

        if trash_name:
            target = trash_dir / trash_name
            if target.exists():
                shutil.rmtree(str(target))
                print(f"  ✅ 已永久删除: {trash_name}")
            else:
                print(f"  ❌ 未找到: {trash_name}")
                return 1
        else:
            count = 0
            for entry in list(trash_dir.iterdir()):
                if entry.is_dir():
                    shutil.rmtree(str(entry))
                    count += 1
            print(f"  ✅ 已永久删除 {count} 项")
        return 0


def _get_outline_manager():
    """Helper: get OutlineManager instance."""
    from scripts.outline.outline_manager import OutlineManager
    return OutlineManager(PROJECT_ROOT)


def _check_outline_gate() -> int:
    """No-outline gate: refuse if active slot has no outline.
    Returns 0 if OK, 1 if blocked.
    """
    try:
        mgr = _get_outline_manager()
        if not mgr.has_active_outline():
            # v0.6.5-clean7: 引导用户放大纲在小说文件夹下
            outline_dir = Path(_get_outline_dir())
            print("=" * 60)
            print("  ⛔ 没有激活的大纲")
            print("=" * 60)
            print()
            print("  当前小说没有激活大纲，不能开写。")
            print()
            print(f"  💡 把大纲.txt放到：{outline_dir}/你的小说名/大纲.txt")
            print()
            print(f"  然后运行 python novel.py outline add")
            return 1
    except Exception as e:
        # If outline module not available, allow pass-through
        pass
    return 0


# ──────────────────────────────────────────────
#  Outline CLI commands
# ──────────────────────────────────────────────

def cmd_outline(args):
    """大纲管理命令"""
    action = getattr(args, "outline_action", None)

    if action == "add":
        return _outline_add(getattr(args, "outline_file", ""),
                           getattr(args, "title", ""),
                           getattr(args, "genre", ""),
                           getattr(args, "style", ""),
                           replace_current=getattr(args, "replace_current", False),
                           keep_inactive=getattr(args, "keep_inactive", False),
                           dry_run=getattr(args, "dry_run", False))
    elif action == "import":
        return _outline_import(getattr(args, "outline_file", ""),
                              getattr(args, "title", ""),
                              getattr(args, "genre", ""),
                              getattr(args, "style", ""))
    elif action == "list":
        return _outline_list()
    elif action == "current":
        return _outline_current()
    elif action == "switch":
        return _outline_switch(getattr(args, "outline_id", ""))
    elif action == "diff":
        return _outline_diff(getattr(args, "id1", ""),
                            getattr(args, "id2", ""))
    elif action == "rollback":
        return _outline_rollback(getattr(args, "outline_id", ""))
    elif action == "compare":
        return _outline_compare(getattr(args, "compare_file", ""))
    elif action == "delete":
        return _outline_delete(getattr(args, "delete_id", ""))
    elif action == "undo":
        return _outline_undo()
    else:
        print("用法: python novel.py outline {add|import|list|current|switch|diff|rollback|compare|delete}")
        print()
        print("  add <文件>              添加大纲（自动相似度检测）")
        print("  import <文件> --title T  导入大纲（指定标题）")
        print("  list                    列出当前工作区所有大纲")
        print("  current                 显示当前激活大纲")
        print("  switch <id>             切换激活大纲")
        print("  diff <id1> <id2>        对比两个大纲")
        print("  rollback <id>           回滚大纲到上一版本")
        print("  compare <文件>           对比文件与当前激活大纲")
        print("  delete <id>             删除指定大纲")
        return 1


def _outline_add(file_path, title="", genre="", style="",
                  replace_current=False, keep_inactive=False, dry_run=False):
    """添加大纲文件 — P0-6/P0-7 智能行为"""
    # v0.6.5-clean7: 无文件时自动扫描 大纲/书名/大纲.txt
    if not file_path:
        nr = Path(_get_outline_dir())
        candidates = []
        if nr.exists():
            for subdir in sorted(nr.iterdir()):
                if subdir.is_dir():
                    of = subdir / "大纲.txt"
                    if of.exists():
                        candidates.append(of)
        if candidates:
            print(f"  📂 扫描 {nr} ...")
            print(f"  找到 {len(candidates)} 个大纲:")
            for i, c in enumerate(candidates, 1):
                try:
                    first = c.read_text(encoding="utf-8").strip().split("\n")[0].lstrip("# ")[:60]
                except Exception:
                    first = "(无法预览)"
                print(f"    [{i}] {c.parent.name}/大纲.txt")
                print(f"        {first}")
            print()
            print(f"  请输入编号 (1-{len(candidates)}) 或完整路径:")
            try:
                choice = input("  > ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(candidates):
                    file_path = str(candidates[idx])
                    print(f"  已选择: {candidates[idx].parent.name}/大纲.txt")
                else:
                    file_path = choice
            except (ValueError, EOFError):
                file_path = choice
            if not file_path:
                print("  ❌ 未选择文件")
                return 1
        else:
            print(f"  💡 未找到大纲。请按此结构放置：")
            print(f"     {nr}/你的小说名/大纲.txt")
            return 1

    fp = Path(file_path)
    if not fp.exists():
        print(f"  ❌ 文件不存在: {file_path}")
        return 1

    content = fp.read_text(encoding="utf-8")

    mgr = _get_outline_manager()

    # 如果已有激活大纲，做相似度检测
    current = mgr.current_outline()
    similarity = None
    if current:
        print("  检测到已有激活大纲，正在进行相似度分析...")
        try:
            from scripts.outline.similarity import OutlineSimilarity
            sim = OutlineSimilarity()
            similarity = sim.compare(
                title1=current.get("title", ""),
                title2=title or fp.stem,
                content1=current.get("content", ""),
                content2=content,
                genre1=current.get("genre", ""),
                genre2=genre,
                style1=current.get("style", ""),
                style2=style,
            )

            score = similarity["similarity_score"]
            cls_cn = {
                "high_similarity": "高相似度",
                "low_similarity": "低相似度",
                "uncertain": "不确定",
            }.get(similarity["classification"], similarity["classification"])

            rec_cn = {
                "upgrade": "建议升级（覆盖原大纲的新版本）",
                "same_novel": "可能是同一部小说",
                "new_novel": "可能是不同小说",
                "ask_user": "请人工确认",
            }.get(similarity["recommendation"], similarity["recommendation"])

            print(f"  📊 相似度得分: {score}/100  ({cls_cn})")
            print(f"  💡 建议: {rec_cn}")
            print()

            # 显示分类明细
            detail = similarity.get("detail", {})
            if detail.get("character_overlap"):
                co = detail["character_overlap"]
                print(f"    角色重叠: {co['score']}分 (共同角色: {', '.join(co['intersection']) if co['intersection'] else '无'})")
            if detail.get("worldbuilding_overlap"):
                wo = detail["worldbuilding_overlap"]
                print(f"    世界观重叠: {wo['score']}分 (共同关键词: {', '.join(wo['intersection'][:5]) if wo['intersection'] else '无'})")
            if detail.get("chapter_structure_similarity"):
                cs = detail["chapter_structure_similarity"]
                s1 = cs.get("outline1", {})
                s2 = cs.get("outline2", {})
                print(f"    章节结构: {cs['score']}分 (旧:{s1.get('chapters',0)}章/{s1.get('volumes',1)}卷 vs 新:{s2.get('chapters',0)}章/{s2.get('volumes',1)}卷)")

            print()

            # ── P0-6: 低相似度 (<35) — 自动创建新 slot ──
            if similarity["recommendation"] == "new_novel" or score < 35:
                print("  🔄 检测到可能是不同的小说。" if similarity["recommendation"] == "new_novel"
                      else "  🔄 相似度低于阈值，判定为新小说。")
                print()

                if dry_run:
                    print("  [--dry-run] 将执行以下操作:")
                    idle = mgr._find_idle_slot()
                    if idle:
                        print(f"  → 使用空闲 slot: {idle}")
                    else:
                        new_id = mgr._get_next_slot_id()
                        print(f"  → 创建新 slot: {new_id}")
                    print(f"  → 将大纲导入新 slot 并切换工作区" if title else f"  → 将「{fp.stem}」导入新 slot 并切换工作区" )
                    print(f"  → 原 slot 不受影响" )
                    print()
                    print("  使用 --replace-current 或 --keep-inactive 覆盖此行为。" )
                    return 0

                print("  → 正在为新小说创建独立工作区..." )
                result = mgr.add_outline_to_new_slot(
                    content=content,
                    title=title or "",
                    genre=genre,
                    style=style,
                    similarity_result=similarity,
                )

                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '创建失败')}" )
                    return 1

                print()
                print("=" * 60)
                print("  ✅ 新小说工作区创建成功！" )
                print("=" * 60)
                print(f"  新 Slot: {result['slot_id']}" )
                print(f"  创建方式: {'新建' if result['slot_created'] else '复用空闲 slot'}" )
                print(f"  大纲 ID: {result['outline_id']}" )
                print(f"  标题: {result['title']}" )
                print(f"  章节数: {result.get('chapter_count', 0)}" )
                if result.get('old_slot'):
                    print(f"  已从 {result['old_slot']} 切换到此工作区" )
                print()
                print("  使用 python novel.py db list 查看所有工作区" )
                return 0

            # ── P0-7: 高相似度 (>=70) — 升级当前大纲 ──
            if similarity["recommendation"] == "upgrade" or score >= 70:
                print("  📝 检测到这是当前小说的大纲升级版。" )

                if dry_run:
                    print(f"  [--dry-run] 相似度 {score}/100，判定为升级版。" )
                    print("  使用 --replace-current 激活为新大纲" )
                    print("  使用 --keep-inactive 保存但不激活" )
                    return 0

                if replace_current:
                    print("  → 正在替换当前激活大纲（旧版将保存为历史版本）..." )
                    result = mgr.add_outline_as_version(
                        content=content,
                        title=title or fp.stem,
                        genre=genre,
                        style=style,
                        similarity_result=similarity,
                        activate=True,
                    )
                elif keep_inactive:
                    print("  → 正在保存为独立大纲（不激活）..." )
                    result = mgr.add_outline_as_version(
                        content=content,
                        title=title or fp.stem,
                        genre=genre,
                        style=style,
                        similarity_result=similarity,
                        activate=False,
                    )
                else:
                    # 无 CLI flag: 询问用户
                    print("  检测到这是当前小说的大纲升级版。是否将它设为当前激活大纲？" )
                    print("  输入 y = 替换当前大纲（旧版保存为历史版本）" )
                    print("  输入 n = 保存但不激活（保留当前激活大纲）" )
                    try:
                        choice = input("  > ").strip().lower()
                    except (EOFError, KeyboardInterrupt):
                        choice = "n"
                    if choice == "y" or choice == "yes":
                        print("  → 替换当前激活大纲..." )
                        result = mgr.add_outline_as_version(
                            content=content,
                            title=title or fp.stem,
                            genre=genre,
                            style=style,
                            similarity_result=similarity,
                            activate=True,
                        )
                    else:
                        print("  → 保存但不激活..." )
                        result = mgr.add_outline_as_version(
                            content=content,
                            title=title or fp.stem,
                            genre=genre,
                            style=style,
                            similarity_result=similarity,
                            activate=False,
                        )

                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '添加失败')}" )
                    return 1

                print()
                print("=" * 60)
                if result.get("mode") == "replace":
                    print("  ✅ 大纲已升级！（旧版已保存为历史版本）" )
                else:
                    print("  ✅ 大纲已保存（未激活，当前激活大纲不变）" )
                print("=" * 60)
                print(f"  ID: {result['id']}" )
                print(f"  标题: {result['title']}" )
                print(f"  章节数: {result.get('chapter_count', 0)}" )
                if result.get("versions_count", 0) > 0:
                    print(f"  历史版本: {result['versions_count']} 个" )
                if result.get("mode") == "inactive":
                    print()
                    print(f"  使用 python novel.py outline switch {result['id']} 激活此大纲" )
                print()
                return 0

            # ── 不确定区域 (35-69): ask_user ──
            print("  ⚠️  相似度处于不确定范围（35-69）。" )
            print("  请手动判断:" )
            print(f"    1 = 同一小说，替换当前大纲" )
            print(f"    2 = 同一小说，保存但不激活" )
            print(f"    3 = 不同小说，创建新工作区" )
            print(f"    4 = 取消" )
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "4"
            # v0.6.5-clean8: 支持 y/n/new/cancel 别名
            if choice in ("y", "yes", "1", "替换"):
                choice = "1"
            elif choice in ("n", "no", "2", "保存", "保留"):
                choice = "2"
            elif choice in ("new", "3", "新建"):
                choice = "3"
            elif choice in ("cancel", "c", "4", "取消"):
                choice = "4"
            if choice == "1":
                print("  → 替换当前激活大纲..." )
                result = mgr.add_outline_as_version(
                    content=content,
                    title=title or fp.stem,
                    genre=genre,
                    style=style,
                    similarity_result=similarity,
                    activate=True,
                )
                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '添加失败')}" )
                    return 1
                print()
                print("=" * 60)
                print("  ✅ 大纲已升级！（旧版保存为历史版本）" )
                print("=" * 60)
                print(f"  ID: {result['id']}" )
                print(f"  标题: {result['title']}" )
                return 0
            elif choice == "2":
                print("  → 保存但不激活..." )
                result = mgr.add_outline_as_version(
                    content=content,
                    title=title or fp.stem,
                    genre=genre,
                    style=style,
                    similarity_result=similarity,
                    activate=False,
                )
                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '添加失败')}" )
                    return 1
                print()
                print("=" * 60)
                print("  ✅ 大纲已保存（未激活）" )
                print("=" * 60)
                print(f"  ID: {result['id']}" )
                print(f"  标题: {result['title']}" )
                return 0
            elif choice == "3":
                print("  → 正在为新小说创建独立工作区..." )
                result = mgr.add_outline_to_new_slot(
                    content=content,
                    title=title or fp.stem,
                    genre=genre,
                    style=style,
                    similarity_result=similarity,
                )
                if result.get("status") == "error":
                    print(f"  ❌ {result.get('message', '创建失败')}" )
                    return 1
                print()
                print("=" * 60)
                print("  ✅ 新小说工作区创建成功！" )
                print("=" * 60)
                print(f"  新 Slot: {result['slot_id']}" )
                print(f"  大纲 ID: {result['outline_id']}" )
                print(f"  标题: {result['title']}" )
                return 0
            else:
                print("  ⏭️  已取消。" )
                return 1

        except ImportError:
            print("  (相似度引擎不可用，跳过检测)" )
        except Exception as e:
            print(f"  (相似度检测异常: {e})" )

    # 无已有大纲或相似度引擎异常：直接添加
    result = mgr.add_outline(
        content=content,
        title=title,
        genre=genre,
        style=style,
        similarity_result=similarity,
    )

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '添加失败')}" )
        return 1

    print("=" * 60)
    print("  ✅ 大纲添加成功！" )
    print("=" * 60)
    print(f"  ID: {result['id']}" )
    print(f"  标题: {result['title']}" )
    print(f"  章节数: {result.get('chapter_count', 0)}" )
    print(f"  卷数: {result.get('volume_count', 1)}" )
    print()
    print("  使用 python novel.py outline list 查看所有大纲" )
    return 0


def _outline_import(file_path, title="", genre="", style=""):
    """导入大纲（指定标题）"""
    fp = Path(file_path)
    if not fp.exists():
        print(f"  ❌ 文件不存在: {file_path}")
        return 1

    if not title:
        print("  ❌ 导入大纲必须指定标题: --title \"小说名称\"")
        return 1

    content = fp.read_text(encoding="utf-8")
    mgr = _get_outline_manager()

    result = mgr.import_outline(
        content=content,
        title=title,
        genre=genre,
        style=style,
    )

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '导入失败')}")
        return 1

    print("=" * 60)
    print("  ✅ 大纲导入成功！")
    print("=" * 60)
    print(f"  ID: {result['id']}")
    print(f"  标题: {result['title']}")
    print(f"  章节数: {result.get('chapter_count', 0)}")
    print()
    return 0


def _outline_list():
    """列出所有大纲，含版本关系显示"""
    mgr = _get_outline_manager()
    outlines = mgr.list_outlines()

    if not outlines:
        print("  当前工作区没有大纲。")
        print("  使用 python novel.py outline add <文件> 添加大纲。")
        return 0

    print("=" * 70)
    print("  大纲列表")
    print("=" * 70)
    print()

    for o in outlines:
        marker = "★" if o.get("active") else " "
        otype = o.get("type", "")
        type_labels = {
            "active": "🔵 当前使用",
            "historical": "📜 历史版本",
            "candidate": "📄 候选大纲",
        }
        type_label = type_labels.get(otype, otype)

        print(f"  {marker} [{o['id']}]  {type_label}")
        print(f"      标题: {o['title']}")
        print(f"      章节: {o.get('chapter_count', 0)} 章 / {o.get('volume_count', 1)} 卷")
        genre = o.get("genre", "")
        style = o.get("style", "")
        if genre or style:
            print(f"      类型/风格: {genre or '-'} / {style or '-'}")
        tags = o.get("tags", [])
        if tags:
            print(f"      标签: {', '.join(tags)}")

        # ── 版本关系 ──
        sv = o.get("source_version")
        if sv:
            print(f"      来源版本: v{sv.get('version', '?')}「{sv.get('title', '')}」({sv.get('saved_at', '')[:19] if sv.get('saved_at') else '未知时间'})")
        else:
            ver_count = o.get('versions_count', 0)
            print(f"      历史版本: {ver_count} 个")

        # ── 相似度 ──
        sim_score = o.get("similarity_score")
        if sim_score is not None:
            similar_to = o.get("similar_to", "")
            if similar_to:
                print(f"      相似度: {sim_score}% → 「{similar_to}」")
            else:
                print(f"      相似度: {sim_score}%")

        print(f"      更新时间: {o.get('updated_at', o.get('created_at', ''))[:19]}")
        print()

    active_count = sum(1 for o in outlines if o.get("type") == "active")
    historical_count = sum(1 for o in outlines if o.get("type") == "historical")
    candidate_count = sum(1 for o in outlines if o.get("type") == "candidate")
    print(f"  共 {len(outlines)} 个大纲：{active_count} 个使用中 / {historical_count} 个历史 / {candidate_count} 个候选")
    return 0


def _outline_current():
    """显示当前激活大纲"""
    mgr = _get_outline_manager()
    current = mgr.current_outline()

    if not current:
        print("  当前没有激活的大纲。")
        print("  使用 python novel.py outline add <文件> 添加大纲。")
        return 1

    print("=" * 60)
    print(f"  当前大纲: {current.get('title', '')}")
    print("=" * 60)
    print(f"  ID: {current.get('id', '')}")
    print(f"  章节数: {current.get('chapter_count', 0)}")
    print(f"  卷数: {current.get('volume_count', 1)}")
    genre = current.get("genre", "")
    style = current.get("style", "")
    if genre or style:
        print(f"  类型/风格: {genre or '-'} / {style or '-'}")
    tags = current.get("tags", [])
    if tags:
        print(f"  标签: {', '.join(tags)}")
    print(f"  版本数: {len(current.get('outline_versions', []))}")
    print(f"  创建时间: {current.get('created_at', '')[:19]}")
    print(f"  更新时间: {current.get('updated_at', '')[:19]}")

    # 相似度检测结果
    sc = current.get("similarity_check")
    if sc:
        cls_cn = {
            "high_similarity": "高相似度",
            "low_similarity": "低相似度",
            "uncertain": "不确定",
        }.get(sc.get("classification", ""), "")
        print()
        print(f"  相似度检测: {sc.get('similarity_score', 0)}/100 ({cls_cn})")

    print()
    print("-" * 60)
    print("  大纲内容预览（前30行）:")
    print("-" * 60)
    content = current.get("content", "")
    lines = content.strip().split("\n")[:30]
    for line in lines:
        print(f"  {line}")
    if len(content.strip().split("\n")) > 30:
        print(f"  ... (共 {len(content.strip().split(chr(10)))} 行)")
    print()

    return 0


def _outline_switch(outline_id):
    """切换激活大纲"""
    if not outline_id:
        print("用法: python novel.py outline switch <outline_id>")
        print("提示: 使用 python novel.py outline list 查看所有大纲ID")
        return 1

    mgr = _get_outline_manager()
    result = mgr.switch_outline(outline_id)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        available = result.get("available", [])
        if available:
            print(f"  可用大纲: {', '.join(available)}")
        return 1

    print(f"  ✅ 已切换到大纲: {result['title']}")
    print(f"  ID: {result['outline_id']}")
    prev = result.get("previous")
    if prev:
        print(f"  (之前: {prev})")
    return 0


def _outline_diff(id1, id2):
    """对比两个大纲"""
    if not id1 or not id2:
        print("用法: python novel.py outline diff <id1> <id2>")
        print("提示: 使用 python novel.py outline list 查看所有大纲ID")
        return 1

    mgr = _get_outline_manager()
    result = mgr.diff_outlines(id1, id2)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1

    print("=" * 60)
    o1 = result.get("outline1", {})
    o2 = result.get("outline2", {})
    print(f"  大纲对比: [{o1.get('id', id1)}] {o1.get('title', '')}  vs  [{o2.get('id', id2)}] {o2.get('title', '')}")
    print("=" * 60)
    print()

    score = result["similarity_score"]
    cls_cn = {
        "high_similarity": "高相似度",
        "low_similarity": "低相似度",
        "uncertain": "不确定",
    }.get(result["classification"], result["classification"])

    rec_cn = {
        "upgrade": "建议升级（覆盖版本）",
        "same_novel": "可能是同一部小说",
        "new_novel": "可能是不同小说",
        "ask_user": "请人工确认",
    }.get(result["recommendation"], result["recommendation"])

    print(f"  📊 综合相似度: {score}/100")
    print(f"  🏷️  分类: {cls_cn}")
    print(f"  💡 建议: {rec_cn}")
    print()

    detail = result.get("detail", {})
    print("  各维度明细:")
    print("  " + "-" * 50)

    # 标题
    ts = detail.get("title_similarity", {})
    print(f"  标题相似度:      {ts.get('score', 0)}分  (权重{ts.get('weight', 0)*100:.0f}%)")
    print(f"    \"{ts.get('title1', '')}\" ↔ \"{ts.get('title2', '')}\"")

    # 角色
    co = detail.get("character_overlap", {})
    print(f"  角色名重叠:      {co.get('score', 0)}分  (权重{co.get('weight', 0)*100:.0f}%)")
    print(f"    大纲1角色: {', '.join(co.get('chars1', [])) or '(无)'}")
    print(f"    大纲2角色: {', '.join(co.get('chars2', [])) or '(无)'}")
    common_chars = co.get("intersection", [])
    print(f"    共同角色: {', '.join(common_chars) if common_chars else '(无)'}")

    # 世界观
    wo = detail.get("worldbuilding_overlap", {})
    print(f"  世界观重叠:      {wo.get('score', 0)}分  (权重{wo.get('weight', 0)*100:.0f}%)")
    common_world = wo.get("intersection", [])
    print(f"    共同关键词: {', '.join(common_world[:10]) if common_world else '(无)'}")

    # 章节结构
    cs = detail.get("chapter_structure_similarity", {})
    print(f"  章节结构相似:    {cs.get('score', 0)}分  (权重{cs.get('weight', 0)*100:.0f}%)")
    s1 = cs.get("outline1", {})
    s2 = cs.get("outline2", {})
    print(f"    大纲1: {s1.get('chapters', 0)}章/{s1.get('volumes', 1)}卷")
    print(f"    大纲2: {s2.get('chapters', 0)}章/{s2.get('volumes', 1)}卷")

    # 类型/风格
    gs = detail.get("genre_style_overlap", {})
    print(f"  题材/风格重叠:   {gs.get('score', 0)}分  (权重{gs.get('weight', 0)*100:.0f}%)")
    g_ol = gs.get("genre_overlap", [])
    s_ol = gs.get("style_overlap", [])
    print(f"    共同题材: {', '.join(g_ol) if g_ol else '(无)'}")
    print(f"    共同风格: {', '.join(s_ol) if s_ol else '(无)'}")

    print()
    return 0


def _outline_rollback(outline_id):
    """回滚大纲"""
    if not outline_id:
        print("用法: python novel.py outline rollback <outline_id>")
        return 1

    mgr = _get_outline_manager()
    result = mgr.rollback_outline(outline_id)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1

    print(f"  ✅ 已回滚大纲「{result['title']}」到版本 {result['rolled_back_to']}")
    print(f"  保存时间: {result.get('saved_at', '')[:19]}")
    print(f"  剩余历史版本: {result.get('versions_remaining', 0)}")
    return 0


def _outline_compare(file_path):
    """对比文件与当前大纲"""
    fp = Path(file_path)
    if not fp.exists():
        print(f"  ❌ 文件不存在: {file_path}")
        return 1

    mgr = _get_outline_manager()
    result = mgr.compare_with_file(file_path)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1

    print("=" * 60)
    o1 = result.get("outline1", {})
    o2 = result.get("outline2", {})
    print(f"  大纲对比: [{o1.get('id', '')}] {o1.get('title', '')}  vs  文件 {o2.get('title', '')}")
    print("=" * 60)
    print()

    score = result["similarity_score"]
    cls_cn = {
        "high_similarity": "高相似度",
        "low_similarity": "低相似度",
        "uncertain": "不确定",
    }.get(result["classification"], result["classification"])

    rec_cn = {
        "upgrade": "可能是当前大纲的新版本",
        "same_novel": "可能是同一部小说",
        "new_novel": "可能是不同小说",
        "ask_user": "请人工确认",
    }.get(result["recommendation"], result["recommendation"])

    print(f"  📊 综合相似度: {score}/100")
    print(f"  🏷️  分类: {cls_cn}")
    print(f"  💡 建议: {rec_cn}")
    print()

    detail = result.get("detail", {})
    print("  各维度明细:")
    print("  " + "-" * 50)
    ts = detail.get("title_similarity", {})
    print(f"  标题相似度:      {ts.get('score', 0)}分")
    co = detail.get("character_overlap", {})
    print(f"  角色名重叠:      {co.get('score', 0)}分")
    common_chars = co.get("intersection", [])
    if common_chars:
        print(f"    共同角色: {', '.join(common_chars)}")
    wo = detail.get("worldbuilding_overlap", {})
    print(f"  世界观重叠:      {wo.get('score', 0)}分")
    common_world = wo.get("intersection", [])
    if common_world:
        print(f"    共同关键词: {', '.join(common_world[:10])}")
    cs = detail.get("chapter_structure_similarity", {})
    print(f"  章节结构相似:    {cs.get('score', 0)}分")
    gs = detail.get("genre_style_overlap", {})
    print(f"  题材/风格重叠:   {gs.get('score', 0)}分")
    print()
    return 0


def _outline_delete(outline_id):
    """删除大纲"""
    if not outline_id:
        print("用法: python novel.py outline delete <outline_id>")
        return 1

    mgr = _get_outline_manager()
    result = mgr.delete_outline(outline_id)

    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1

    print(f"  ✅ 已删除大纲「{result.get('title', outline_id)}」")
    new_active = result.get("new_active")
    if new_active:
        print(f"  ℹ️  激活大纲已自动切换为: {new_active}")
    elif new_active is None and result.get("new_active") is not None:
        print(f"  ⚠️  当前工作区已无大纲，请添加新大纲。")
    return 0


def _outline_undo():
    """v0.6.5-clean7: 撤销最近一次 outline add"""
    mgr = _get_outline_manager()
    result = mgr.undo_last_add()
    if result.get("status") == "error":
        print(f"  ❌ {result.get('message', '')}")
        return 1
    print(f"  ✅ {result.get('message', '')}")
    return 0


# ═══════════════════════════════════════════════════════════════
#  scc-help — 中文用户手册
# ═══════════════════════════════════════════════════════════════

def cmd_scc_help():
    """打印中文用户手册。"""
    print("=" * 68)
    print("  小说写作流水线 — 操作手册")
    v = get_version()
    print(f"  Write Engine {v}")
    print("=" * 68)
    print()
    print("  novel.py 是所有操作的统一入口。")
    print()
    print("  ── Hermes/Agent 用户 ──")
    print("  如果你是 Hermes Agent 用户，可以直接用自然语言与我对话：")
    print("  · 说「我要写第3章」→ 我会检查上下文并生成任务卡")
    print("  · 说「添加大纲」→ 我会引导你上传或粘贴大纲内容")
    print("  · 说「审稿第1章」→ 我会运行 Agent 陪审团审查")
    print("  · 说「导出小说」→ 我会帮你导出 Markdown")
    print("  · 说「菜单」→ 我会显示交互式中文菜单")
    print()
    print("  ── CLI/终端用户 ──")
    print("  以下按功能分类列出常用命令。")
    print()

    # ── 1. 新用户从这里开始 ──
    print("  " + "─" * 60)
    print("  【新用户从这里开始】")
    print("  " + "─" * 60)
    print("  python novel.py init                初始化项目（目录 + 数据库 + 配置）")
    print("  python novel.py status              检查环境状态（Python/配置/文件完整性）")
    print("  python novel.py status --detail     详细诊断模式")
    print("  python novel.py demo                运行演示流水线（创建示例章节并跑全部守卫）")
    print("  python novel.py pre <章节号>         生成写前任务卡（上下文/伏笔/规则）")
    print("  python novel.py post <章节号>        写后守卫检查 + 入库")
    print("  python novel.py board               只读项目看板（总览状态）")
    print()

    # ── 2. 大纲管理 ──
    print("  " + "─" * 60)
    print("  【大纲管理】outline")
    print("  " + "─" * 60)
    print("  python novel.py outline add <文件>       添加大纲（自动相似度检测）")
    print("  python novel.py outline import <文件>    导入大纲（--title 必须指定标题）")
    print("  python novel.py outline list             列出当前工作区所有大纲")
    print("  python novel.py outline current          显示当前激活大纲")
    print("  python novel.py outline switch <id>      切换激活大纲")
    print("  python novel.py outline diff <id1> <id2> 对比两个大纲（相似度分析）")
    print("  python novel.py outline rollback <id>    回滚大纲到上一版本")
    print("  python novel.py outline compare <文件>    对比文件与当前激活大纲")
    print("  python novel.py outline delete <id>      删除指定大纲")
    print()

    # ── 3. 数据库管理 ──
    print("  " + "─" * 60)
    print("  【数据库管理】db")
    print("  " + "─" * 60)
    print("  python novel.py db init              初始化 workspace 目录结构")
    print("  python novel.py db list              列出所有 DB slot（★=当前活跃）")
    print("  python novel.py db current           显示当前活跃 DB slot")
    print("  python novel.py db info              显示当前 slot 详细信息")
    print("  python novel.py db new --name <名>    创建新 DB slot")
    print("  python novel.py db use <slot_id>     切换 DB slot")
    print("  python novel.py db backup            备份当前 slot 的 project.json")
    print("  python novel.py db delete <slot_id>  删除指定 DB slot（不能删当前活跃的）")
    print("  python novel.py db restore <slot_id> 从备份恢复 DB slot")
    print()

    # ── 4. Agent 陪审团 ──
    print("  " + "─" * 60)
    print("  【Agent 陪审团】agents")
    print("  " + "─" * 60)
    print("  python novel.py agents review <章> --mode light   轻量模式审查（快）")
    print("  python novel.py agents review <章> --mode full    完整模式审查（详细）")
    print("  python novel.py agents review <章> --genre xianxia  指定题材风格")
    print()

    # ── 5. Story Contract ──
    print("  " + "─" * 60)
    print("  【Story Contract 故事合同系统】story")
    print("  " + "─" * 60)
    print("  python novel.py story init                 初始化 .story/ 目录")
    print("  python novel.py story contract <章>         生成章节合同（约束 + 伏笔）")
    print("  python novel.py story commit <章>           生成章节提交记录")
    print("  python novel.py story health                故事链健康检查")
    print("  python novel.py post <章> --story           写后守卫 + 自动生成 commit")
    print()

    # ── 6. 记忆与规则 ──
    print("  " + "─" * 60)
    print("  【记忆与规则】query / learn")
    print("  " + "─" * 60)
    print("  python novel.py query <问题>        查询项目记忆（角色/伏笔/世界观）")
    print("  python novel.py learn list          列出已学写作规则")
    print("  python novel.py learn add <规则>    添加写作规则")
    print("  python novel.py learn remove <编号> 删除写作规则")
    print()

    # ── 7. 导出与报告 ──
    print("  " + "─" * 60)
    print("  【导出与报告】report / export")
    print("  " + "─" * 60)
    print("  python novel.py report                  显示最近守卫报告")
    print("  python novel.py guards                  列出注册的守卫及状态")
    print("  python novel.py check <文件>            对指定章节文件运行守卫检查")
    print("  python novel.py export --slug <id>      导出为 Markdown（默认）")
    print("  python novel.py export --slug <id> --format txt  导出为纯文本")
    print("  python novel.py wc <章节号|文件>         统计中文字数")
    print()

    # ── 8. 其他工具 ──
    print("  " + "─" * 60)
    print("  【其他工具】genre / style / rag / review")
    print("  " + "─" * 60)
    print("  python novel.py genre list              列出可用题材包")
    print("  python novel.py genre show <id>         查看题材包详情")
    print("  python novel.py style list              列出可用风格包")
    print("  python novel.py style show <id>         查看风格包详情")
    print("  python novel.py rag status              查看 RAG 状态（向量/全文搜索）")
    print("  python novel.py rag query <问题>        语义搜索小说数据库")
    print("  python novel.py review <章>             运行守卫审查")
    print()

    # ── 9. 常见问题 ──
    print("  " + "━" * 60)
    print("  【常见问题 FAQ】")
    print("  " + "━" * 60)
    print()
    print("  Q: 为什么 pre/post/write 提示「没有激活的大纲」？")
    print("  A: 必须先添加大纲才能开始写作。")
    print("     1) 把大纲 .txt 文件放到「大纲」文件夹（如 D:\\小说\\大纲\\）")
    print("     2) 执行: python novel.py outline add D:\\小说\\大纲\\大纲.txt")
    print("     或在 Hermes 里直接说「添加大纲」")
    print()
    print("  Q: 如何开始一部新小说？")
    print("  A: 推荐流程：")
    print("     1) 在 D:\\小说\\大纲\\ 下创建小说大纲 .txt 文件")
    print("     2) python novel.py outline add <大纲路径>    # 自动检测相似度，不同小说自动创建新 slot")
    print("     3) python novel.py pre 1                      # 生成第1章任务卡")
    print("     4) python novel.py post 1                     # 写完后入库 + 守卫检查")
    print()
    print("  Q: outline upgrade 和 db new 有什么区别？")
    print("  A: 同一部小说的新大纲用 outline add（自动检测相似度，建议升级）")
    print("     不同小说用 db new 创建独立工作区（数据互不干扰）")
    print()
    print("  Q: 数据库文件在哪里？")
    print("  A: 每个 DB slot 在 workspace/<slot_id>/ 下有独立的 novel.db。")
    print("     例如当前活跃 slot 的数据库: workspace/<active_slot>/novel.db")
    print("     config.json 中 db_path 字段也可以指定自定义路径。")
    print()
    print("  Q: 如何查看完整帮助？")
    print("  A: python novel.py --help      查看所有命令列表")
    print("     python novel.py <命令> --help 查看具体命令的用法")
    print("     python novel.py menu         进入交互式菜单")
    print()
    print("  " + "━" * 60)
    print("  使用 python novel.py menu 进入交互式菜单")
    print("  " + "━" * 60)
    print()
    return 0


# ═══════════════════════════════════════════════════════════════
#  menu — 交互式文本菜单
# ═══════════════════════════════════════════════════════════════

def _menu_show_header():
    """显示菜单顶部信息栏（当前 slot + 大纲）。"""
    v = get_version()
    print()
    print("=" * 64)
    print(f"  小说写作流水线 Write Engine {v}")
    print("=" * 64)

    # 当前 DB slot
    try:
        import json as _json
        ws_dir = PROJECT_ROOT / "workspace"
        reg = ws_dir / "registry.json"
        if reg.exists():
            data = _json.loads(reg.read_text(encoding="utf-8"))
            active = data.get("active_slot", "")
            slot_name = ""
            for s in data.get("slots", []):
                if s.get("id") == active:
                    slot_name = s.get("name", "")
                    break
            print(f"  DB Slot: {active} ({slot_name})" if slot_name else f"  DB Slot: {active}")
        else:
            print("  DB Slot: (未初始化)")
    except Exception:
        print("  DB Slot: (读取失败)")

    # 当前大纲
    try:
        mgr = _get_outline_manager()
        cur = mgr.current_outline()
        if cur:
            print(f"  大纲: {cur.get('title', '')} [{cur.get('id', '')}]  "
                  f"{cur.get('chapter_count', 0)}章/{cur.get('volume_count', 1)}卷")
        else:
            print("  大纲: (未设定)")
    except Exception:
        print("  大纲: (不可用)")

    print("-" * 64)


def _menu_confirm_dangerous(prompt_text="确认执行此操作？"):
    """危险操作确认：要求输入 YES。"""
    print()
    print(f"  ⚠️  {prompt_text}")
    answer = input("  输入 YES 确认，其他任意键取消: ").strip()
    return answer == "YES"


def _menu_db_management():
    """子菜单：数据库管理。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【数据库管理】")
        print("  " + "─" * 50)
        print("  [1] db list        列出所有 DB slot")
        print("  [2] db current     显示当前活跃 slot")
        print("  [3] db info        显示当前 slot 详细信息")
        print("  [4] db new         创建新 DB slot")
        print("  [5] db use         切换 DB slot")
        print("  [6] db backup      备份当前 slot")
        print("  [7] db delete      删除 DB slot")
        print("  [8] db restore     从备份恢复")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-8]: ").strip()

        if choice == "1":
            _db_list()
        elif choice == "2":
            _db_current()
        elif choice == "3":
            _db_info()
        elif choice == "4":
            name = input("  请输入新 slot 名称: ").strip()
            if name:
                desc = input("  描述（可选）: ").strip()
                _db_new(name, desc)
            else:
                print("  ❌ 名称不能为空。")
        elif choice == "5":
            slot_id = input("  请输入 slot ID（如 slot_002）: ").strip()
            if slot_id:
                _db_use(slot_id)
        elif choice == "6":
            _db_backup()
        elif choice == "7":
            slot_id = input("  请输入要删除的 slot ID: ").strip()
            if slot_id and _menu_confirm_dangerous(f"将删除 slot {slot_id}。此操作不可逆！"):
                _db_delete(slot_id)
        elif choice == "8":
            slot_id = input("  请输入要恢复的 slot ID: ").strip()
            if slot_id:
                _db_restore(slot_id)
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_outline_management():
    """子菜单：大纲管理。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【大纲管理】")
        print("  " + "─" * 50)
        print("  [1] outline add       添加大纲")
        print("  [2] outline import    导入大纲（指定标题）")
        print("  [3] outline list      列出所有大纲")
        print("  [4] outline current   显示当前激活大纲")
        print("  [5] outline switch    切换激活大纲")
        print("  [6] outline diff      对比两个大纲")
        print("  [7] outline rollback  回滚大纲版本")
        print("  [8] outline compare   对比文件与当前大纲")
        print("  [9] outline delete    删除大纲")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-9]: ").strip()

        if choice == "1":
            fp = input("  大纲文件路径: ").strip()
            if fp:
                title = input("  标题（可选）: ").strip()
                genre = input("  题材（可选）: ").strip()
                style = input("  风格（可选）: ").strip()
                _outline_add(fp, title, genre, style)
        elif choice == "2":
            fp = input("  大纲文件路径: ").strip()
            if fp:
                title = input("  标题（必填）: ").strip()
                if not title:
                    print("  ❌ 标题不能为空。")
                else:
                    genre = input("  题材（可选）: ").strip()
                    style = input("  风格（可选）: ").strip()
                    _outline_import(fp, title, genre, style)
        elif choice == "3":
            _outline_list()
        elif choice == "4":
            _outline_current()
        elif choice == "5":
            oid = input("  大纲 ID: ").strip()
            if oid:
                _outline_switch(oid)
        elif choice == "6":
            id1 = input("  大纲1 ID: ").strip()
            id2 = input("  大纲2 ID: ").strip()
            if id1 and id2:
                _outline_diff(id1, id2)
        elif choice == "7":
            oid = input("  大纲 ID: ").strip()
            if oid:
                _outline_rollback(oid)
        elif choice == "8":
            fp = input("  文件路径: ").strip()
            if fp:
                _outline_compare(fp)
        elif choice == "9":
            oid = input("  大纲 ID: ").strip()
            if oid and _menu_confirm_dangerous(f"将删除大纲 {oid}。"):
                _outline_delete(oid)
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_writing_flow():
    """子菜单：写作流程。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【写作流程】")
        print("  " + "─" * 50)
        print("  [1] pre <章>        生成写前任务卡")
        print("  [2] post <章>       写后守卫检查 + 入库")
        print("  [3] post <章> --story  写后守卫 + 自动生成 story commit")
        print("  [4] review <章>     运行守卫审查")
        print("  [5] check <文件>    对指定文件运行守卫检查")
        print("  [6] wc <章|文件>    统计中文字数")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-6]: ").strip()

        if choice == "1":
            ch = input("  章节号: ").strip()
            if ch:
                cmd_pre(ch)
        elif choice == "2":
            ch = input("  章节号: ").strip()
            if ch:
                cmd_post(ch)
        elif choice == "3":
            ch = input("  章节号: ").strip()
            if ch:
                cmd_post(ch, story=True)
        elif choice == "4":
            ch = input("  章节号: ").strip()
            if ch:
                cmd_review(ch)
        elif choice == "5":
            fp = input("  文件路径: ").strip()
            if fp:
                cmd_check(fp)
        elif choice == "6":
            fp = input("  章节号或文件路径: ").strip()
            if fp:
                cmd_wc(fp)
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_agents():
    """子菜单：Agent 陪审团。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【Agent 陪审团】")
        print("  " + "─" * 50)
        print("  [1] light 模式审查（快速）")
        print("  [2] full 模式审查（详细）")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-2]: ").strip()

        if choice in ("1", "2"):
            ch = input("  章节号: ").strip()
            if ch:
                mode = "light" if choice == "1" else "full"
                try:
                    from scripts.agents.orchestrator import run_agent_review
                    slug = _get_default_slug()
                    novels_root = Path(_get_novels_root())
                    ch_dir = novels_root / slug / "第01卷"
                    candidates = list(ch_dir.glob(f"第{ch}章*.txt"))
                    content = ""
                    if candidates:
                        content = candidates[0].read_text(encoding="utf-8")
                    result = run_agent_review(content, int(ch), mode=mode)
                    print(f"  Score: {result.get('overall_score', 'N/A')}")
                    print(f"  Status: {result.get('status', 'N/A')}")
                    chief = result.get("chief_editor", {})
                    for cat in ["must_fix", "should_fix", "keep"]:
                        items = chief.get(cat, [])
                        if items:
                            print(f"  {cat}: {len(items)} items")
                except Exception as e:
                    print(f"  [ERROR] Agent review failed: {e}")
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_story_contract():
    """子菜单：Story Contract。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【Story Contract 故事合同】")
        print("  " + "─" * 50)
        print("  [1] story init          初始化 .story/")
        print("  [2] story contract      生成章节合同")
        print("  [3] story commit        生成章节提交记录")
        print("  [4] story health        故事链健康检查")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-4]: ").strip()

        if choice == "1":
            if _story_exists():
                print("  .story/ 目录已存在。如需重建请先删除。")
            else:
                try:
                    from scripts.story import story_init
                    result = story_init.init_story(PROJECT_ROOT)
                    print(f"  [OK] .story/ 已初始化")
                    for item in result.get("created", []):
                        print(f"    + {item}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "2":
            if not _story_exists():
                print(f"  {_story_missing_msg()}")
            else:
                ch = input("  章节号: ").strip() or "1"
                try:
                    from scripts.story import contract_builder
                    contract = contract_builder.build_contract(PROJECT_ROOT, int(ch))
                    saved = contract_builder.save_contract(PROJECT_ROOT, int(ch), contract)
                    print(f"  [OK] 第{ch}章合同已生成: {saved}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "3":
            if not _story_exists():
                print(f"  {_story_missing_msg()}")
            else:
                ch = input("  章节号: ").strip() or "1"
                try:
                    from scripts.story import commit_builder
                    commit = commit_builder.build_commit(PROJECT_ROOT, int(ch), chapter_title=f"第{ch}章")
                    saved = commit_builder.save_commit(PROJECT_ROOT, int(ch), commit)
                    print(f"  [OK] 第{ch}章提交记录已生成: {saved}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "4":
            if not _story_exists():
                print(f"  {_story_missing_msg()}")
            else:
                try:
                    from scripts.story import story_health
                    report = story_health.check_health(PROJECT_ROOT)
                    print(f"  状态: {report['status']}")
                    print(f"  合同数: {report.get('contract_count', 0)}")
                    print(f"  提交数: {report.get('commit_count', 0)}")
                    print(f"  事件数: {report.get('event_count', 0)}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_reports_exports():
    """子菜单：报告与导出。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【报告与导出】")
        print("  " + "─" * 50)
        print("  [1] report        显示最近守卫报告")
        print("  [2] guards        列出注册守卫")
        print("  [3] export MD     导出为 Markdown")
        print("  [4] export TXT    导出为纯文本")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-4]: ").strip()

        if choice == "1":
            cmd_report()
        elif choice == "2":
            cmd_guards()
        elif choice == "3":
            slug = input("  小说 slug: ").strip()
            if slug:
                cmd_export(slug, "md")
        elif choice == "4":
            slug = input("  小说 slug: ").strip()
            if slug:
                cmd_export(slug, "txt")
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def _menu_advanced():
    """子菜单：高级命令。"""
    while True:
        print()
        print("  " + "─" * 50)
        print("  【高级命令】")
        print("  " + "─" * 50)
        print("  [1] genre list         列出可用题材包")
        print("  [2] style list         列出可用风格包")
        print("  [3] rag status         查看 RAG 状态")
        print("  [4] rag query          语义搜索数据库")
        print("  [5] query <问题>       查询项目记忆")
        print("  [6] learn list         列出已学规则")
        print("  [7] learn add          添加写作规则")
        print("  [8] wc <章|文件>       统计中文字数")
        print("  [9] board              项目看板")
        print("  [0] 返回主菜单")
        print()
        choice = input("  请选择 [0-9]: ").strip()

        if choice == "1":
            try:
                from scripts.genre.genre_loader import list_genres
                genres = list_genres()
                print(f"  Available genres ({len(genres)}):")
                for g in genres:
                    print(f"    {g}")
            except Exception as e:
                print(f"  [ERROR] {e}")
        elif choice == "2":
            try:
                from scripts.genre.style_loader import list_styles
                styles = list_styles()
                print(f"  Available styles ({len(styles)}):")
                for s in styles:
                    print(f"    {s}")
            except Exception as e:
                print(f"  [ERROR] {e}")
        elif choice == "3":
            try:
                from scripts.rag.rag_config import load_rag_config, get_rag_mode
                cfg = load_rag_config()
                mode = get_rag_mode(cfg)
                print(f"  RAG Mode: {mode}")
            except Exception as e:
                print(f"  RAG: FTS5 (default). Vector: unavailable ({e})")
        elif choice == "4":
            q = input("  问题: ").strip()
            if q:
                try:
                    from scripts.rag.rag_query import rag_query
                    result = rag_query(q)
                    print(f"  Mode: {result.get('mode', 'fts5')}")
                    for r in result.get("results", [])[:5]:
                        print(f"    [{r.get('chapter_no', '?')}] {r.get('evidence', '')[:80]}")
                except Exception as e:
                    print(f"  [ERROR] {e}")
        elif choice == "5":
            q = input("  问题: ").strip()
            if q:
                # Build a simple args-like object for cmd_query
                class _Args:
                    pass
                a = _Args()
                a.question = [q]
                cmd_query(a)
        elif choice == "6":
            class _Args:
                pass
            a = _Args()
            a.action = "list"
            a.rule = []
            cmd_learn(a)
        elif choice == "7":
            rule = input("  规则内容: ").strip()
            if rule:
                class _Args:
                    pass
                a = _Args()
                a.action = "add"
                a.rule = [rule]
                cmd_learn(a)
        elif choice == "8":
            fp = input("  章节号或文件路径: ").strip()
            if fp:
                cmd_wc(fp)
        elif choice == "9":
            cmd_board(None)
        elif choice == "0":
            break
        else:
            print("  无效选择，请重试。")


def cmd_chapters():
    """v0.6.5-clean7: 列出当前活跃 slot 的所有章节及字数."""
    import json as _json, sqlite3 as _sql
    ws = PROJECT_ROOT / "workspace"
    reg_file = ws / "registry.json"
    if not reg_file.exists():
        print("  workspace 未初始化。")
        return 1

    reg = _json.loads(reg_file.read_text(encoding="utf-8"))
    active = reg.get("active_slot", "")
    if not active:
        print("  没有活跃 slot。")
        return 1

    slot_dir = ws / active
    db_path = slot_dir / "novel.db"
    if not db_path.exists():
        print(f"  {active} 没有 novel.db")
        return 1

    conn = _sql.connect(str(db_path))
    conn.row_factory = _sql.Row
    rows = conn.execute(
        "SELECT chapter_no, title, word_count, status, created_at FROM chapters ORDER BY chapter_no"
    ).fetchall()
    # Also get novel title
    novel_row = conn.execute("SELECT title FROM novels LIMIT 1").fetchone()
    novel_title = novel_row["title"] if novel_row else active
    conn.close()

    print()
    print(f"  📖 {novel_title} ({active})")
    print(f"  " + "─" * 50)
    if not rows:
        print("  (暂无章节)")
    else:
        total_wc = 0
        for r in rows:
            total_wc += r["word_count"] or 0
            print(f"  第{r['chapter_no']:02d}章  {r['title'] or '(无标题)':20s}  {r['word_count'] or 0:>5,}字  [{r['status']}]")
        print(f"  " + "─" * 50)
        print(f"  共 {len(rows)} 章，{total_wc:,} 字")
    print()
    return 0


def cmd_menu_show():
    """v0.6.5-clean8: 普通用户菜单（纯文本）"""
    from scripts.hermes_menu import get_project_status, render_main_menu
    status = get_project_status()
    print(render_main_menu(status))
    return 0


def cmd_menu_text():
    """v0.6.5-clean8: 输出项目状态 JSON，供 Hermes 静默调用"""
    import json as _json
    from scripts.hermes_menu import get_project_status
    status = get_project_status()
    print(_json.dumps(status, ensure_ascii=False))
    return 0


def cmd_setup():
    """v0.6.5-clean7: 交互式设置 — 引导用户配置小说文件夹路径."""
    import json as _json
    cfg_file = PROJECT_ROOT / "config.json"

    print()
    print("  " + "=" * 55)
    print("  📁 项目设置 — 配置小说文件夹")
    print("  " + "=" * 55)
    print()

    # Read current
    try:
        cfg = _json.loads(cfg_file.read_text(encoding="utf-8"))
    except Exception:
        cfg = {"novels_root": "./novels", "paths": {}}

    current = cfg.get("novels_root", "未设置")
    print(f"  当前小说文件夹: {current}")
    print()
    print("  你的小说章节文件放在哪个文件夹？")
    print("  例如: D:\\小说  或  E:\\我的小说")
    print()
    print("  提示:")
    print("  · 文件夹下会自动创建「大纲/」「导出/」子目录")
    print("  · 每部小说会有自己的子文件夹")
    print("  · 可以随时修改")
    print()

    try:
        new_path = input("  请输入路径 (回车保留当前): ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return 0

    if not new_path:
        print("  已取消，保持原设置。")
        return 0

    # Validate
    from pathlib import Path
    p = Path(new_path)
    if not p.is_absolute():
        print(f"  ⚠️ 请输入完整路径（如 D:\\小说），不要用相对路径。")
        return 1

    # Create directory if needed
    try:
        p.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"  ⚠️ 无法创建目录: {e}")

    # Save
    if "paths" not in cfg:
        cfg["paths"] = {}
    cfg["novels_root"] = str(p)
    cfg["paths"]["novels_root"] = str(p)
    cfg_file.write_text(_json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print(f"  ✅ 小说文件夹已设置为: {p}")
    print(f"     每部小说一个子文件夹，大纲、章节、导出都在里面")
    print()
    print(f"  现在把大纲.txt放到小说文件夹（如 {p / '旧楼深处/大纲.txt'}），")
    print(f"  然后运行 python novel.py outline add")
    print()
    return 0


def cmd_menu():
    """交互式文本菜单 — 用 input() 实现的纯终端菜单。"""
    while True:
        _menu_show_header()

        print("  主菜单:")
        print("  " + "─" * 40)
        print("  [1] 新手检查      项目初始化、状态诊断、演示")
        print("  [2] 数据库管理    DB slot 创建/切换/备份/恢复")
        print("  [3] 大纲管理      添加/列出/切换/对比/回滚")
        print("  [4] 写作流程      pre → 写作 → post → review")
        print("  [5] Agent 陪审团   AI 审查（light / full 模式）")
        print("  [6] Story Contract 故事合同系统")
        print("  [7] 报告与导出    守卫报告、导出小说")
        print("  [8] 操作手册      打印完整中文手册")
        print("  [9] 高级命令      genre/style/RAG/learn/query")
        print("  [S] 项目设置      设置小说文件夹路径")
        print("  [0] 退出")
        print()
        choice = input("  请选择 [0-9/S]: ").strip()

        if choice == "1":
            # 新手检查
            while True:
                print()
                print("  " + "─" * 50)
                print("  【新手检查】")
                print("  " + "─" * 50)
                print("  [1] init        初始化项目")
                print("  [2] status      环境诊断")
                print("  [3] status --detail  详细诊断")
                print("  [4] demo        运行演示")
                print("  [5] board       项目看板")
                print("  [0] 返回主菜单")
                print()
                sub = input("  请选择 [0-5]: ").strip()
                if sub == "1":
                    cmd_init()
                elif sub == "2":
                    cmd_status(detail=False)
                elif sub == "3":
                    cmd_status(detail=True)
                elif sub == "4":
                    cmd_demo()
                elif sub == "5":
                    cmd_board(None)
                elif sub == "0":
                    break
                else:
                    print("  无效选择，请重试。")

        elif choice == "2":
            _menu_db_management()

        elif choice == "3":
            _menu_outline_management()

        elif choice == "4":
            _menu_writing_flow()

        elif choice == "5":
            _menu_agents()

        elif choice == "6":
            _menu_story_contract()

        elif choice == "7":
            _menu_reports_exports()

        elif choice == "8":
            print()
            cmd_scc_help()

        elif choice == "9":
            _menu_advanced()

        elif choice.upper() == "S":
            cmd_setup()

        elif choice.upper() == "C":
            cmd_chapters()

        elif choice == "0":
            print()
            print("  再见！")
            print()
            break

        else:
            print("  无效选择，请重试。")

    return 0


def cmd_stability_check(args=None):
    """P2-1: 稳定性自检 — 输出评分和问题清单.
    v0.6.5-clean4: 默认快速模式，--full 运行 pytest+demo.
    """
    import subprocess as _sp
    import importlib

    full_mode = getattr(args, "full", False)

    print("=" * 60)
    mode_label = "完整模式 (pytest + demo)" if full_mode else "快速模式"
    print(f"  Novel Pipeline - 稳定性自检 ({mode_label})")
    print(f"  版本: {get_version()}")
    print("=" * 60)
    print()

    score = 100
    p0_issues = []
    p1_issues = []
    checks = []

    # 1. 版本号一致
    try:
        vfile = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        v = get_version()
        ok = v == vfile
        checks.append(("版本号一致性", ok, f"VERSION={vfile}, get_version()={v}"))
        if not ok:
            p0_issues.append("VERSION 文件与代码版本不一致")
            score -= 10
    except Exception as e:
        checks.append(("版本号一致性", False, str(e)))
        p0_issues.append(f"无法读取版本号: {e}")
        score -= 10

    # 2. config 可解析
    try:
        cfg = _load_project_config()
        checks.append(("配置文件", True, "config.json 可解析"))
    except Exception as e:
        checks.append(("配置文件", False, str(e)))
        p0_issues.append(f"config.json 解析失败: {e}")
        score -= 10

    # 3. workspace 初始化
    ws_dir = PROJECT_ROOT / "workspace"
    ws_ok = ws_dir.exists() and (ws_dir / "registry.json").exists()
    checks.append(("workspace 初始化", ws_ok, str(ws_dir)))
    if not ws_ok:
        p1_issues.append("workspace 未初始化，请运行 python novel.py db init")
        score -= 5

    # 4. 默认 3 slot 完整
    if ws_ok:
        try:
            import json as _json
            reg = _json.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
            slots = reg.get("slots", [])
            slot_ok = len(slots) >= 3
            checks.append(("默认 slot 完整", slot_ok, f"{len(slots)} 个 slot"))
            if not slot_ok:
                p0_issues.append(f"仅有 {len(slots)} 个默认 slot，需要 3 个")
                score -= 10
        except Exception as e:
            checks.append(("默认 slot 完整", False, str(e)))
            score -= 5

    # 5. active slot 有 novel.db
    try:
        from scripts.db.slot_manager import SlotManager
        sm = SlotManager(PROJECT_ROOT)
        if sm.registry.exists():
            active = sm.registry.get_active_slot()
            db_path = sm.get_slot_db_path(active) if active else None
            db_ok = db_path and db_path.exists()
            checks.append(("active slot DB", db_ok, str(db_path) if db_path else "无活跃 slot"))
            if not db_ok:
                p0_issues.append(f"活跃 slot {active} 缺少 novel.db")
                score -= 10
        else:
            checks.append(("active slot DB", False, "registry 不存在"))
    except Exception as e:
        checks.append(("active slot DB", False, str(e)))
        p1_issues.append(f"无法检查 DB: {e}")
        score -= 5

    # 6. agent 数量达标
    agents_dir = PROJECT_ROOT / "configs" / "jury" / "agents"
    agent_count = len(list(agents_dir.glob("*.yaml"))) if agents_dir.exists() else 0
    agent_ok = agent_count >= 15
    checks.append(("Agent 数量", agent_ok, f"{agent_count} 个 (需要 >=15)"))
    if not agent_ok:
        p0_issues.append(f"Agent 仅 {agent_count} 个，目标 >=15")
        score -= 10

    # 7. pytest (--full only, v0.6.5-clean5: 防挂 + 禁用插件)
    if full_mode:
        try:
            import os as _os
            env = {**_os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
            result = _sp.run(
                [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=short"],
                cwd=str(PROJECT_ROOT), timeout=180,
                capture_output=True, text=True, env=env
            )
            test_ok = result.returncode == 0
            checks.append(("pytest", test_ok, f"exit={result.returncode}"))
            if not test_ok:
                # Show last 3 lines of stderr for debugging
                err_lines = result.stderr.strip().split("\n")[-3:]
                p0_issues.append(f"pytest 运行失败 (exit={result.returncode})")
                score -= 10
        except _sp.TimeoutExpired:
            checks.append(("pytest", False, "超时 (180s)"))
            p0_issues.append("pytest 超时，可能挂起")
            score -= 15
        except Exception as e:
            checks.append(("pytest", False, str(e)[:60]))
            p1_issues.append(f"pytest 无法运行: {e}")
            score -= 5
    else:
        checks.append(("pytest", True, "跳过（使用 --full 运行）"))

    # 8. 交叉平台检查
    cp_script = PROJECT_ROOT / "scripts" / "cross_platform_check.py"
    if cp_script.exists():
        try:
            cp = _sp.run([sys.executable, str(cp_script)], cwd=str(PROJECT_ROOT),
                         timeout=30, capture_output=True, text=True)
            cp_ok = cp.returncode == 0
            checks.append(("交叉平台", cp_ok, "通过" if cp_ok else "有警告"))
            if not cp_ok:
                p1_issues.append("交叉平台检查有警告")
                score -= 5
        except Exception:
            checks.append(("交叉平台", False, "超时/异常"))
            score -= 5

    # 9. story contract 是否存在断链
    story_dir = PROJECT_ROOT / ".story"
    if story_dir.exists():
        try:
            from scripts.story import story_health
            health = story_health.check_health(PROJECT_ROOT)
            h_ok = health["status"] == "OK"
            checks.append(("Story 健康", h_ok, health["status"]))
            if health["status"] == "FAIL":
                p0_issues.append(f"Story 链断裂: {len(health.get('failures', []))} 项")
                score -= 10
            elif health["status"] == "WARN":
                p1_issues.append(f"Story 链警告: {len(health.get('warnings', []))} 项")
                score -= 5
        except Exception as e:
            checks.append(("Story 健康", False, str(e)))

    # 10. v0.6.5-clean3: Slot FTS 完整性检查
    try:
        import sqlite3
        ws_dir = PROJECT_ROOT / "workspace"
        fts_issues = []
        for slot_dir in sorted(ws_dir.glob("slot_*")):
            db_path = slot_dir / "novel.db"
            if not db_path.exists():
                continue
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='novel_chapter_fts'")
            if not cur.fetchone():
                fts_issues.append(f"{slot_dir.name} 缺少 FTS5 表")
            conn.close()
        fts_ok = len(fts_issues) == 0
        detail = "所有 slot 有 FTS5" if fts_ok else f"{len(fts_issues)} 个 slot 缺 FTS5"
        checks.append(("Slot FTS 完整性", fts_ok, detail))
        if not fts_ok:
            p0_issues.append(f"Slot DB 缺 FTS5 表: {', '.join(fts_issues)}")
            score -= 10
    except Exception as e:
        checks.append(("Slot FTS 完整性", False, str(e)))
        p1_issues.append(f"无法检查 slot FTS: {e}")
        score -= 5

    # 11. v0.6.5-clean9: --full 真跑 demo（stdin=DEVNULL 防交互挂起）
    if full_mode:
        try:
            import os as _os
            demo_result = _sp.run(
                [sys.executable, "novel.py", "demo"],
                cwd=str(PROJECT_ROOT), timeout=180,
                capture_output=True, text=True,
                stdin=_sp.DEVNULL
            )
            demo_ok = demo_result.returncode == 0
            detail = "demo 通过" if demo_ok else f"demo 失败 (exit={demo_result.returncode})"
            checks.append(("Demo 验证", demo_ok, detail))
            if not demo_ok:
                # Show last few lines of output
                lines = (demo_result.stdout + demo_result.stderr).strip().split("\n")
                last = "\n".join(lines[-5:]) if lines else "(无输出)"
                p0_issues.append(f"Demo 运行失败: {last[:200]}")
                score -= 20
        except _sp.TimeoutExpired:
            checks.append(("Demo 验证", False, "超时 (180s)"))
            p0_issues.append("Demo 运行超时")
            score -= 20
        except Exception as e:
            checks.append(("Demo 验证", False, str(e)[:60]))
            p1_issues.append(f"Demo 检查异常: {e}")
            score -= 5
    else:
        checks.append(("Demo 验证", True, "跳过（使用 --full 运行）"))

    # 输出结果
    for name, ok, detail in checks:
        icon = "✓" if ok else "✗"
        print(f"  [{icon}] {name}: {detail}")

    print()
    print("=" * 60)
    print(f"  稳定性评分: {max(0, score)}/100")
    print(f"  P0 问题: {len(p0_issues)} 个")
    print(f"  P1 问题: {len(p1_issues)} 个")

    if p0_issues:
        print(f"\n  P0 必须修复:")
        for iss in p0_issues:
            print(f"    ✗ {iss}")
    if p1_issues:
        print(f"\n  P1 建议修复:")
        for iss in p1_issues:
            print(f"    ⚠ {iss}")

    if p0_issues:
        print(f"\n  建议: 不建议发布（存在 P0 问题，必须先修复）")
    elif score >= 80:
        print(f"\n  建议: 可以发布正式版")
    elif score >= 60:
        print(f"\n  建议: 修复 P1 问题后再发布")
    else:
        print(f"\n  建议: 不建议发布")
    print("=" * 60)
    return 0 if not p0_issues and score >= 80 else 1


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=f"Novel Pipeline - Write Engine {get_version()} CLI",
    )
    parser.add_argument('--version', action='version',
                        version=f'Novel Pipeline - Write Engine {get_version()}')
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # status
    p_status = sub.add_parser("status", help="Run environment diagnostics")
    p_status.add_argument("--detail", action="store_true", help="Show detailed output")
    # doctor (same as status --detail)
    p_doctor = sub.add_parser("doctor", help="Run detailed environment diagnostics (alias for status --detail)")
    p_doctor.add_argument("--detail", action="store_true", default=True, help="Show detailed output (default on)")
    # demo
    sub.add_parser("demo", help="Run demo pipeline")
    # init
    sub.add_parser("init", help="Initialize project directories and database")
    # pre
    p_pre = sub.add_parser("pre", help="Generate pre-write task card")
    p_pre.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_pre.add_argument("--slug", help="Novel slug")
    p_pre.add_argument("--volume", help="Volume number")
    # post
    p_post = sub.add_parser("post", help="Post-write: run guards and ingest")
    p_post.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_post.add_argument("--slug", help="Novel slug")
    p_post.add_argument("--volume", help="Volume number")
    p_post.add_argument("--file", help="Direct chapter file path")
    p_post.add_argument("--story", action="store_true", help="Auto-generate story commit after post")
    # review
    p_review = sub.add_parser("review", help="Run guard review on a chapter")
    p_review.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_review.add_argument("--slug", help="Novel slug")
    p_review.add_argument("--volume", help="Volume number")
    # report
    sub.add_parser("report", help="Show recent guard reports")
    # guards
    sub.add_parser("guards", help="List registered guards")
    # check
    p_check = sub.add_parser("check", help="Run guard checks on a chapter file")
    p_check.add_argument("file_path", help="Path to chapter TXT file")
    # agents
    p_agents = sub.add_parser("agents", help="Multi-agent review board")
    p_agents_sub = p_agents.add_subparsers(dest="agents_action")
    p_agents_review = p_agents_sub.add_parser("review", help="Run agent review on a chapter")
    p_agents_review.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_agents_review.add_argument("--mode", default="light", choices=["light", "full"])
    p_agents_review.add_argument("--slug", help="Novel slug")
    p_agents_review.add_argument("--genre", help="Genre pack ID (e.g. xianxia, mystery)")
    p_agents_review.add_argument("--style", default=None, help="Style pack ID (e.g. webnovel, black_humor)")
    p_agents_list = p_agents_sub.add_parser("list", help="List all available agents")
    p_agents_list.add_argument("--mode", default=None, help="Filter by mode (light/full/strict/webnovel)")

    # rag
    p_rag = sub.add_parser("rag", help="Vector RAG (optional)")
    p_rag_sub = p_rag.add_subparsers(dest="rag_action")
    p_rag_status = p_rag_sub.add_parser("status", help="Check RAG status")
    p_rag_query = p_rag_sub.add_parser("query", help="Query the novel database")
    p_rag_query.add_argument("question", nargs="*", help="Question to ask")

    # export
    p_export = sub.add_parser("export", help="Export novel to single file")
    p_export.add_argument("--slug", help="Novel slug to export")
    p_export.add_argument("--format", default="md", choices=["txt", "md"])
    # db — Multi-DB workspace management
    p_db = sub.add_parser("db", help="Multi-DB workspace management")
    p_db_sub = p_db.add_subparsers(dest="db_action")
    p_db_sub.add_parser("list", help="列出所有 DB slot")
    p_db_sub.add_parser("current", help="显示当前活跃 DB slot")
    p_db_sub.add_parser("info", help="显示当前 slot 详细信息")
    p_db_new = p_db_sub.add_parser("new", help="创建新 DB slot")
    p_db_new.add_argument("--name", required=True, help="Slot 名称")
    p_db_new.add_argument("--description", default="", help="Slot 描述")
    p_db_use = p_db_sub.add_parser("use", help="切换到指定 DB slot")
    p_db_use.add_argument("slot_id", help="Slot ID (如 slot_001)")
    p_db_delete = p_db_sub.add_parser("delete", help="安全删除 DB slot (移至回收站)")
    p_db_delete.add_argument("slot_id", help="Slot ID")
    p_db_delete.add_argument("--yes", action="store_true", help="确认删除")
    p_db_sub.add_parser("trash", help="查看回收站中的 slot")
    p_db_restore = p_db_sub.add_parser("restore", help="从备份或回收站恢复 DB slot")
    p_db_restore.add_argument("slot_id", help="Slot ID 或回收站项目名")
    p_db_restore.add_argument("--backup-id", help="备份 ID (不指定则使用最新备份)")
    p_db_restore.add_argument("--from-trash", action="store_true", help="从回收站恢复 (默认从备份恢复)")
    p_db_purge = p_db_sub.add_parser("purge", help="永久删除回收站中的 slot")
    p_db_purge.add_argument("trash_name", nargs="?", default=None, help="回收站项目名 (不指定则清空全部)")
    p_db_backup = p_db_sub.add_parser("backup", help="备份当前 DB slot")
    p_db_backup.add_argument("--slot", help="Slot ID (默认当前活跃)")
    p_db_init = p_db_sub.add_parser("init", help="初始化 workspace 目录结构")
    p_db_init.add_argument("--force", action="store_true", help="强制重新初始化")
    # outline — 大纲管理
    p_outline = sub.add_parser("outline", help="大纲管理（添加/列出/切换/对比/回滚）")
    p_outline_sub = p_outline.add_subparsers(dest="outline_action")
    p_outline_add = p_outline_sub.add_parser("add", help="添加大纲（自动相似度检测与智能处理）")
    p_outline_add.add_argument("outline_file", nargs="?", default="", help="大纲文件路径 (.txt)，留空自动扫描 大纲/")
    p_outline_add.add_argument("--title", default="", help="大纲标题")
    p_outline_add.add_argument("--genre", default="", help="题材")
    p_outline_add.add_argument("--style", default="", help="风格")
    p_outline_add.add_argument("--replace-current", action="store_true",
                                help="高相似度时替换当前激活大纲（P0-7）")
    p_outline_add.add_argument("--keep-inactive", action="store_true",
                                help="高相似度时保存但不激活（P0-7）")
    p_outline_add.add_argument("--dry-run", action="store_true",
                                help="仅显示相似度分析结果，不执行实际操作")
    p_outline_import = p_outline_sub.add_parser("import", help="导入大纲（指定标题）")
    p_outline_import.add_argument("outline_file", help="大纲文件路径 (.txt)")
    p_outline_import.add_argument("--title", required=True, help="大纲标题")
    p_outline_import.add_argument("--genre", default="", help="题材")
    p_outline_import.add_argument("--style", default="", help="风格")
    p_outline_sub.add_parser("list", help="列出所有大纲")
    p_outline_sub.add_parser("current", help="显示当前激活大纲")
    p_outline_switch = p_outline_sub.add_parser("switch", help="切换激活大纲")
    p_outline_switch.add_argument("outline_id", help="大纲 ID")
    p_outline_diff = p_outline_sub.add_parser("diff", help="对比两个大纲")
    p_outline_diff.add_argument("id1", help="大纲1 ID")
    p_outline_diff.add_argument("id2", help="大纲2 ID")
    p_outline_rollback = p_outline_sub.add_parser("rollback", help="回滚大纲到上一版本")
    p_outline_rollback.add_argument("outline_id", help="大纲 ID")
    p_outline_compare = p_outline_sub.add_parser("compare", help="对比文件与当前激活大纲")
    p_outline_compare.add_argument("compare_file", help="文件路径 (.txt)")
    p_outline_delete = p_outline_sub.add_parser("delete", help="删除指定大纲")
    p_outline_delete.add_argument("delete_id", help="大纲 ID")
    p_outline_sub.add_parser("undo", help="撤销最近一次大纲添加")
    # wc
    p_wc = sub.add_parser("wc", help="Count Chinese characters in a chapter file")
    p_wc.add_argument("file_path", nargs="?", help="Path to chapter TXT file")
    # story
    p_story = sub.add_parser("story", help="Story contract system")
    p_story_sub = p_story.add_subparsers(dest="story_action")
    p_story_sub.add_parser("init", help="Initialize .story/ directory")
    p_story_sub_contract = p_story_sub.add_parser("contract", help="Generate chapter contract")
    p_story_sub_contract.add_argument("chapter_no", nargs="?", default="1")
    p_story_sub_commit = p_story_sub.add_parser("commit", help="Generate chapter commit")
    p_story_sub_commit.add_argument("chapter_no", nargs="?", default="1")
    p_story_sub.add_parser("health", help="Check story chain health")

    # query
    p_query = sub.add_parser("query", help="Query project memory")
    p_query.add_argument("question", nargs="*", help="Natural language question")

    # learn
    p_learn = sub.add_parser("learn", help="Writing rules learned")
    p_learn.add_argument("action", nargs="?", default="list")
    p_learn.add_argument("rule", nargs="*", help="Rule text to add")

    # board
    sub.add_parser("board", help="Readonly status board")

    # genre
    p_genre = sub.add_parser("genre", help="Genre pack management")
    p_genre_sub = p_genre.add_subparsers(dest="genre_action")
    p_genre_sub.add_parser("list", help="List available genres")
    p_genre_show = p_genre_sub.add_parser("show", help="Show genre pack details")
    p_genre_show.add_argument("genre_id", help="Genre ID (e.g. xianxia)")
    # style
    p_style = sub.add_parser("style", help="Style pack management")
    p_style_sub = p_style.add_subparsers(dest="style_action")
    p_style_sub.add_parser("list", help="List available styles")
    p_style_show = p_style_sub.add_parser("show", help="Show style pack details")
    p_style_show.add_argument("style_id", help="Style ID (e.g. black_humor)")
    # scc-help — 中文用户手册
    sub.add_parser("scc-help", help="打印中文操作手册")
    sub.add_parser("help", help="打印中文操作手册 (同 scc-help)")
    # menu — 交互式文本菜单
    sub.add_parser("menu", help="进入交互式文本菜单")
    sub.add_parser("scc-menu", help="进入交互式文本菜单 (同 menu)")
    # P2-3: 中文别名（自然语言入口）
    sub.add_parser("start", help="进入交互式文本菜单 (同 menu)")
    sub.add_parser("books", help="列出所有作品 (同 db list)")
    sub.add_parser("outlines", help="列出所有大纲 (同 outline list)")
    p_write = sub.add_parser("write", help="写前任务卡 (同 pre)")
    p_write.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_submit = sub.add_parser("submit", help="写后入库 (同 post)")
    p_submit.add_argument("chapter_no", nargs="?", help="Chapter number")
    p_jury = sub.add_parser("jury", help="轻量审稿 (同 agents review --mode light)")
    p_jury.add_argument("chapter_no", nargs="?", help="Chapter number")
    # P2-1: stability-check
    p_sc = sub.add_parser("stability-check", help="运行稳定性自检，输出评分和问题清单")
    p_sc.add_argument("--full", action="store_true", help="完整模式（含 pytest + demo）")
    # v0.6.5-clean7: setup + chapters
    sub.add_parser("setup", help="设置小说文件夹路径")
    sub.add_parser("chapters", help="列出当前作品所有章节")
    # v0.6.5-clean8: Hermes menu
    sub.add_parser("menu-show", help="显示普通用户菜单（纯文本）")
    sub.add_parser("menu-text", help="输出项目状态 JSON（供 Hermes 调用）")

    args = parser.parse_args()

    if args.command == "status":
        sys.exit(cmd_status(detail=getattr(args, "detail", False)))
    elif args.command == "doctor":
        sys.exit(cmd_doctor(detail=getattr(args, "detail", True)))
    elif args.command == "demo":
        sys.exit(cmd_demo())
    elif args.command == "init":
        sys.exit(cmd_init())
    elif args.command == "pre":
        sys.exit(cmd_pre(getattr(args, "chapter_no", None),
                        getattr(args, "slug", None),
                        getattr(args, "volume", None)))
    elif args.command == "post":
        sys.exit(cmd_post(getattr(args, "chapter_no", None),
                         getattr(args, "slug", None),
                         getattr(args, "volume", None),
                         getattr(args, "file", None),
                         getattr(args, "story", False)))
    elif args.command == "review":
        sys.exit(cmd_review(getattr(args, "chapter_no", None),
                           getattr(args, "slug", None),
                           getattr(args, "volume", None)))
    elif args.command == "report":
        sys.exit(cmd_report())
    elif args.command == "guards":
        sys.exit(cmd_guards())
    elif args.command == "check":
        sys.exit(cmd_check(args.file_path))
    elif args.command == "agents":
        sys.exit(cmd_agents(args))
    elif args.command == "rag":
        sys.exit(cmd_rag(args))
    elif args.command == "export":
        sys.exit(cmd_export(args.slug, args.format))
    elif args.command == "wc":
        sys.exit(cmd_wc(args.file_path))
    elif args.command == "genre":
        sys.exit(cmd_genre(args))
    elif args.command == "style":
        sys.exit(cmd_style(args))
    elif args.command == "story":
        sys.exit(cmd_story(args))
    elif args.command == "query":
        sys.exit(cmd_query(args))
    elif args.command == "learn":
        sys.exit(cmd_learn(args))
    elif args.command == "board":
        sys.exit(cmd_board(args))
    elif args.command == "db":
        sys.exit(cmd_db(args))
    elif args.command == "outline":
        sys.exit(cmd_outline(args))
    elif args.command in ("scc-help", "help"):
        sys.exit(cmd_scc_help())
    elif args.command in ("menu", "scc-menu", "start"):
        sys.exit(cmd_menu())
    elif args.command == "books":
        sys.exit(cmd_db(argparse.Namespace(db_action="list")))
    elif args.command == "outlines":
        import argparse as _ap
        sys.exit(cmd_outline(_ap.Namespace(outline_action="list")))
    elif args.command == "write":
        sys.exit(cmd_pre(getattr(args, "chapter_no", None), None, None))
    elif args.command == "submit":
        sys.exit(cmd_post(getattr(args, "chapter_no", None), None, None, None, False))
    elif args.command == "jury":
        import argparse as _ap
        ch = getattr(args, "chapter_no", None)
        if not ch:
            print("用法: python novel.py jury <章节号>")
            sys.exit(1)
        sys.exit(cmd_agents(_ap.Namespace(agents_action="review", chapter_no=ch, mode="light", slug=None, genre=None, style=None)))
    elif args.command == "stability-check":
        sys.exit(cmd_stability_check(args))
    elif args.command == "setup":
        sys.exit(cmd_setup())
    elif args.command == "chapters":
        sys.exit(cmd_chapters())
    elif args.command == "menu-show":
        sys.exit(cmd_menu_show())
    elif args.command == "menu-text":
        sys.exit(cmd_menu_text())
    else:
        # P2-2: 友好的"我该做什么"提示
        print("=" * 50)
        print(f"  Novel Pipeline - Write Engine {get_version()}")
        print("=" * 50)
        print()
        print("  你现在可以：")
        print()
        print("  0. 首次使用   →  python novel.py setup     # 设置小说文件夹")
        print("  1. 交互菜单   →  python novel.py start")
        print("  2. 检查环境   →  python novel.py status")
        print("  3. 添加大纲   →  python novel.py outline add")
        print("  4. 查看作品   →  python novel.py books")
        print("  5. 开始写作   →  python novel.py write 1")
        print("  6. 审稿       →  python novel.py jury 1")
        print("  7. 导出小说   →  python novel.py export --slug demo_novel")
        print("  8. 运行演示   →  python novel.py demo")
        print()
        print("  详细帮助 →  python novel.py scc-help")
        print("  交互菜单 →  python novel.py menu")
        print("=" * 50)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        # Silently exit on broken pipe (e.g., | head)
        pass
