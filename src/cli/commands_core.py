#!/usr/bin/env python3
"""src/cli/commands_core.py — CLI commands for novel-pipeline-write-engine v0.6.5"""

from src.cli.shared import PROJECT_ROOT, SCRIPTS_DIR, _load_project_config, _cfg_path, _get_default_slug, _get_novels_root, _get_outline_dir, _resolve_post_context, _story_exists, _story_missing_msg, _get_workspace_dir, _get_active_db_path, _get_outline_manager, _check_outline_gate, _get_story_dir
import sys
import json
from pathlib import Path
from datetime import datetime
from version import get_version
from config_utils import normalize_config, load_json_config, resolve_path

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
    print(f"  章节文件：workspace/slot_001/chapters/{slot_ch_file.name}")
    print(f"  兼容副本：{chapter_file}")
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
        from guard_registry import GUARD_RUNNERS, GUARD_LEVELS, MODE_GUARDS
        for name in sorted(GUARD_RUNNERS):
            level = GUARD_LEVELS.get(name, "?")
            print(f"    L{level} {name}")
    except ImportError:
        print("    (guard_registry not importable)")

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


def cmd_post(chapter_no: str = None, slug: str = None, volume_no: str = None, file_path: str = None, story: bool = False, no_jury: bool = False):
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
        # v0.6.6: Auto-run pre if pipeline_state missing
        ch_no_str = str(chapter_no) if chapter_no else "1"
        state_path = PROJECT_ROOT / "exports" / "pipeline_state" / f"chapter_{int(ch_no_str):03d}_state.json"
        if not state_path.exists():
            print(f"  [pre] 未检测到任务卡状态，自动运行 pre...")
            pre_cmd = [sys.executable, str(SCRIPTS_DIR / "chapter_pipeline.py"), "pre",
                       ch_no_str, "--config", str(cfg), "--novel-slug", slug]
            if volume_no: pre_cmd.extend(["--volume-no", str(volume_no)])
            pre_result = subprocess.run(pre_cmd, cwd=str(PROJECT_ROOT), timeout=120)
            if pre_result.returncode != 0:
                print(f"  [pre] 自动 pre 失败，请手动运行 python novel.py pre {ch_no_str}")
                return pre_result.returncode
            print(f"  [pre] 任务卡已生成，继续 post...\n")
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

        # Auto-run agent jury after post (default ON, use --no-jury to skip)
        if not no_jury and result.returncode == 0:
            try:
                print()
                print("  [jury] 自动运行 Agent 陪审团...")
                ch_no = int(chapter_no) if chapter_no else 1
                import argparse as _ap
                _ns = _ap.Namespace(
                    agents_action="review", chapter_no=str(ch_no),
                    mode="light", slug=slug, genre=None, style=None
                )
                cmd_agents(_ns)
            except Exception as e:
                print(f"  [jury] 跳过: {e}")

        return result.returncode
    except Exception as e:
        print(f"  [ERROR] {e}")
        return 1


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
            seen = set()
            for part in parts:
                m = _re.match(r'第(\d+)章\s+(.+)', part.strip())
                if m:
                    ch_num = int(m.group(1))
                    if ch_num in seen:
                        continue
                    seen.add(ch_num)
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
            print(f"[ERROR] 找不到第{chapter_no}章文件 (目录: {ch_dir})")
            print(f"  请指定 --slug 参数，如: python novel.py agents review {chapter_no} --slug 格物证道")
            return 1
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
            prev_commit_path = _get_story_dir() / "commits" / f"chapter_{chapter_no-1:03d}_commit.json"
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
        contract_path = _get_story_dir() / "chapters" / f"chapter_{chapter_no:03d}_contract.json"
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

    story = _get_story_dir()

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

    rules_file = _get_story_dir() / "memory" / "learned_rules.json"
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
    print("  Novel Forge — 项目看板")
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

    # Config — read from active slot's project.json
    cfg = PROJECT_ROOT / "config.json"
    if cfg.exists():
        import json as _json
        try:
            cfg_data = _load_project_config()
            genre = cfg_data.get("default_genre", "?")
            style = cfg_data.get("default_style", "?")
            # v0.6.6: Read project title from active slot
            title = cfg_data.get("default_novel_slug", "?")
            try:
                ws_dir = PROJECT_ROOT / "workspace"
                reg = _json.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
                active = reg.get("active_slot", "")
                proj_file = ws_dir / active / "project.json"
                if proj_file.exists():
                    proj = _json.loads(proj_file.read_text(encoding="utf-8"))
                    title = proj.get("title", proj.get("name", title))
            except Exception:
                pass
            print(f"  当前项目: {title}")
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
            # v0.6.6: resolve slug from active slot
            slot_slug = None
            try:
                ws_dir = PROJECT_ROOT / "workspace"
                reg = _json.loads((ws_dir / "registry.json").read_text(encoding="utf-8"))
                act = reg.get("active_slot", "")
                pf = ws_dir / act / "project.json"
                if pf.exists():
                    pj = _json.loads(pf.read_text(encoding="utf-8"))
                    slot_slug = pj.get("title") or pj.get("name")
            except Exception:
                pass
            slug = slot_slug or cfg_data.get("default_novel_slug", "demo_novel")
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


def cmd_stability_check(args=None):
    """P2-1: 稳定性自检 — 输出评分和问题清单.
    v0.6.5-clean11: 默认快速模式，--full 运行 pytest+structure check.
    """
    import subprocess as _sp
    import importlib

    full_mode = getattr(args, "full", False)

    print("=" * 60)
    mode_label = "完整模式 (pytest + structure check)" if full_mode else "快速模式"
    print(f"  Novel Forge - 稳定性自检 ({mode_label})")
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
        p1_issues.append("workspace 未初始化——首次使用请先运行 python novel.py init（或 python novel.py demo 一键全流程）")
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

    # 6. agent 数量达标（Python Agent 类数）
    agents_py_dir = PROJECT_ROOT / "scripts" / "agents"
    agent_count = len([f for f in agents_py_dir.glob("*_agent.py") if f.name != "base_agent.py" and f.name != "disabled_example_agent.py"]) if agents_py_dir.exists() else 0
    agent_ok = agent_count >= 15
    checks.append((f"Agent 类", agent_ok, f"{agent_count} 个 (需要 >=15)"))
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
    story_dir = _get_story_dir()
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

    # 11. v0.6.5-clean10: --full 轻量结构自检（不跑 demo 子进程，防挂）
    if full_mode:
        try:
            smoke_ok = True
            smoke_parts = []

            # a) slot_001 DB 表完整性
            import sqlite3
            db = PROJECT_ROOT / "workspace" / "slot_001" / "novel.db"
            if db.exists():
                conn = sqlite3.connect(str(db))
                tables = [r[0] for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()]
                conn.close()
                has_chapters = "chapters" in tables
                has_fts = any("fts" in t for t in tables)
                smoke_parts.append("DB✓" if (has_chapters and has_fts) else "DB✗")
                if not has_chapters or not has_fts:
                    smoke_ok = False
            else:
                smoke_parts.append("DB✗")
                smoke_ok = False

            # b) config 可解析
            cfg_path = PROJECT_ROOT / "config.json"
            smoke_parts.append("CFG✓" if cfg_path.exists() else "CFG✗")

            # c) workspace 初始化
            ws = PROJECT_ROOT / "workspace"
            has_reg = (ws / "registry.json").exists()
            smoke_parts.append("WS✓" if has_reg else "WS✗")
            if not has_reg:
                smoke_ok = False

            # d) agents 配置存在
            agents = [f for f in (PROJECT_ROOT / "scripts" / "agents").glob("*_agent.py") if f.name != "base_agent.py" and f.name != "disabled_example_agent.py"]
            smoke_parts.append(f"Agents:{len(agents)}")
            if len(agents) < 15:
                smoke_ok = False

            checks.append(("结构自检", smoke_ok, " ".join(smoke_parts)))
            if not smoke_ok:
                p0_issues.append("结构自检未通过（DB/WS/Agents 不完整）")
                score -= 20
        except Exception as e:
            checks.append(("结构自检", False, str(e)[:60]))
            p0_issues.append(f"结构自检异常: {e}")
            score -= 20
    else:
        checks.append(("结构自检", True, "跳过（使用 --full 运行）"))

    # 12. v0.6.5-clean11: demo 全流程运行测试 (--full only)
    if full_mode:
        try:
            demo = _sp.run(
                [sys.executable, str(PROJECT_ROOT / "novel.py"), "demo"],
                cwd=str(PROJECT_ROOT), timeout=120,
                capture_output=True, text=True
            )
            demo_ok = demo.returncode == 0
            # Also check stderr for import errors
            stderr_clean = "No module named" not in demo.stderr and "Traceback" not in demo.stderr
            detail = f"exit={demo.returncode}"
            if not stderr_clean:
                detail += " stderr=有异常"
            checks.append(("demo 全流程", demo_ok and stderr_clean, detail))
            if not demo_ok or not stderr_clean:
                # Show last lines of stderr for debugging
                err_tail = demo.stderr.strip().split("\n")[-3:]
                p0_issues.append(f"demo 全流程失败 (exit={demo.returncode}): {'; '.join(err_tail)}")
                score -= 20
        except _sp.TimeoutExpired:
            checks.append(("demo 全流程", False, "超时 (120s)"))
            p0_issues.append("demo 全流程超时")
            score -= 15
        except Exception as e:
            checks.append(("demo 全流程", False, str(e)[:60]))
            p1_issues.append(f"demo 无法运行: {e}")
            score -= 5
    else:
        checks.append(("demo 全流程", True, "跳过（使用 --full 运行）"))

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

