#!/usr/bin/env python3
"""
health_check.py — 健康检查入口脚本 v0.5.0

Thin wrapper around src/cli/commands_status.py.
Also provides a direct implementation for environments where the src package
is not importable.

Usage:
  python scripts/health_check.py
  python scripts/health_check.py --direct   (force direct implementation)
  python scripts/health_check.py --json     (JSON output)

Exit codes:
  0 = PASS (all checks passed)
  1 = WARNING (some non-critical checks failed)
  2 = FAIL (critical checks failed)
"""

import sys
import os
import json
import sqlite3
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# Ensure src is importable
_src_path = PROJECT_ROOT
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))


# ═══════════════════════════════════════════════════
# Option 1: Thin wrapper (delegates to commands_status)
# ═══════════════════════════════════════════════════

def run_via_status_module() -> int:
    """Delegate to src/cli/commands_status.py main()."""
    try:
        from src.cli.commands_status import main as status_main
        return status_main()
    except ImportError as e:
        print(f"[WARN] Cannot import src.cli.commands_status: {e}")
        print("[INFO] Falling back to direct implementation.")
        return None
    except Exception as e:
        print(f"[WARN] Status module error: {e}")
        print("[INFO] Falling back to direct implementation.")
        return None


# ═══════════════════════════════════════════════════
# Option 2: Direct implementation
# ═══════════════════════════════════════════════════

from version import get_version as _gv; EXPECTED_VERSION = _gv()

CRITICAL_CHECKS = {
    "python_version",
    "dependencies",
    "config",
    "sqlite",
}

WARNING_CHECKS = {
    "fts5",
    "voice_packs",
    "meme_packs",
    "demo_project",
    "guard_registry",
    "reports_dir",
    "readme_version",
    "release_notes",
}


def _icon(passed: bool) -> str:
    return "[OK]" if passed else "[FAIL]"


def check_python_version() -> bool:
    """Python >= 3.10"""
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 10)
    print(f"  {_icon(ok)} Python {major}.{minor} (>= 3.10)")
    return ok


def check_dependencies() -> bool:
    """Core dependencies importable."""
    required = ["sqlite3", "json", "argparse", "re", "pathlib"]
    all_ok = True
    for mod in required:
        try:
            __import__(mod)
            print(f"  [OK] {mod}")
        except ImportError:
            print(f"  [FAIL] {mod} — not found")
            all_ok = False
    return all_ok


def check_config() -> bool:
    """config.json or config.example.json exists."""
    candidates = [
        PROJECT_ROOT / "config.json",
        PROJECT_ROOT / "config.example.json",
    ]
    for c in candidates:
        if c.exists():
            print(f"  [OK] Config: {c.name}")
            return True
    print(f"  [FAIL] No config.json or config.example.json")
    return False


def _get_db_path() -> str | None:
    """Extract db_path from config."""
    for cfg_name in ("config.json", "config.example.json"):
        cfg = PROJECT_ROOT / cfg_name
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                return data.get("db_path")
            except Exception:
                pass
    return None


def check_sqlite() -> bool:
    """SQLite DB connectable."""
    db_path = _get_db_path()
    if not db_path:
        print(f"  [FAIL] SQLite — cannot determine DB path from config")
        return False

    full_path = Path(db_path)
    if not full_path.is_absolute():
        full_path = PROJECT_ROOT / db_path

    if not full_path.exists():
        print(f"  [FAIL] SQLite — DB file not found: {full_path}")
        return False

    try:
        conn = sqlite3.connect(f"file:{full_path}?mode=ro", uri=True)
        conn.execute("SELECT 1")
        conn.close()
        print(f"  [OK] SQLite connected: {full_path}")
        return True
    except Exception as e:
        print(f"  [FAIL] SQLite error: {e}")
        return False


def check_fts5() -> bool:
    """FTS5 virtual tables available."""
    db_path = _get_db_path()
    if not db_path:
        print(f"  [FAIL] FTS5 — no DB path")
        return False

    full_path = Path(db_path)
    if not full_path.is_absolute():
        full_path = PROJECT_ROOT / db_path

    if not full_path.exists():
        print(f"  [FAIL] FTS5 — DB file not found")
        return False

    try:
        conn = sqlite3.connect(f"file:{full_path}?mode=ro", uri=True)
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%fts%'"
        )
        rows = cur.fetchall()
        conn.close()
        if rows:
            print(f"  [OK] FTS5 — {len(rows)} virtual table(s): {', '.join(r[0] for r in rows[:4])}")
            return True
        else:
            print(f"  [FAIL] FTS5 — no virtual tables found")
            return False
    except Exception as e:
        print(f"  [FAIL] FTS5 check error: {e}")
        return False


def check_voice_packs() -> bool:
    """voice_packs/ directory exists with content."""
    vp = PROJECT_ROOT / "voice_packs"
    if vp.exists() and vp.is_dir():
        children = list(vp.iterdir())
        count = len(children)
        print(f"  [OK] voice_packs/ — {count} entries")
        return count > 0
    print(f"  [FAIL] voice_packs/ — not found")
    return False


def check_meme_packs() -> bool:
    """voice_packs/memes/ directory with content."""
    mp = PROJECT_ROOT / "voice_packs" / "memes"
    if mp.exists() and mp.is_dir():
        json_files = list(mp.glob("*.json"))
        count = len(json_files)
        print(f"  [OK] meme_packs/ — {count} JSON files")
        return count > 0
    print(f"  [FAIL] meme_packs/ — not found")
    return False


def check_demo_project() -> bool:
    """Demo project / outline skeleton exists."""
    demo = PROJECT_ROOT / "examples" / "demo_novel" / "outline_skeleton.json"
    if demo.exists():
        print(f"  [OK] Demo project: {demo.name}")
        return True
    # Also check for outline_skeleton.json at project root
    alt = PROJECT_ROOT / "outline_skeleton.json"
    if alt.exists():
        print(f"  [OK] Demo project: outline_skeleton.json")
        return True
    print(f"  [FAIL] Demo project — outline_skeleton.json not found")
    return False


def check_guard_registry() -> bool:
    """Guard registry importable and valid."""
    scripts_dir = SCRIPT_DIR
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from guard_registry import GUARD_LEVELS, MODE_GUARDS
        guard_count = len(GUARD_LEVELS)
        mode_count = len(MODE_GUARDS)
        print(f"  [OK] Guard registry — {guard_count} guards, {mode_count} modes")
        return True
    except ImportError as e:
        print(f"  [FAIL] Guard registry — import failed: {e}")
        return False
    except Exception as e:
        print(f"  [FAIL] Guard registry — {e}")
        return False


def check_reports_dir() -> bool:
    """reports/ directory exists and writable."""
    rpt = PROJECT_ROOT / "reports"
    if not rpt.exists():
        try:
            rpt.mkdir(parents=True, exist_ok=True)
            print(f"  [OK] reports/ created and writable")
            return True
        except Exception as e:
            print(f"  [FAIL] reports/ cannot create: {e}")
            return False

    test_file = rpt / ".health_test"
    try:
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        print(f"  [OK] reports/ writable")
        return True
    except Exception as e:
        print(f"  [FAIL] reports/ not writable: {e}")
        return False


def check_readme_version() -> bool:
    """README version matches EXPECTED_VERSION."""
    import re
    readme = PROJECT_ROOT / "README.md"
    if not readme.exists():
        print(f"  [FAIL] README.md not found")
        return False
    try:
        content = readme.read_text(encoding="utf-8")
        first_line = content.split("\n")[0]
        m = re.search(r"v\d+\.\d+\.\d+", first_line)
        if m:
            found = m.group(0)
            match = found == EXPECTED_VERSION
            icon = _icon(match)
            tag = "(match)" if match else f"(expected {EXPECTED_VERSION})"
            print(f"  {icon} README version: {found} {tag}")
            return match
        print(f"  [FAIL] README — no version in title line")
        return False
    except Exception as e:
        print(f"  [FAIL] README check error: {e}")
        return False


def check_release_notes() -> bool:
    """docs/releases/ directory has release notes."""
    rel = PROJECT_ROOT / "docs" / "releases"
    if rel.exists() and rel.is_dir():
        md_files = list(rel.glob("*.md"))
        if md_files:
            print(f"  [OK] Release notes — {len(md_files)} file(s): {md_files[0].name}")
            return True
        print(f"  [FAIL] Release notes — no .md files in docs/releases/")
        return False
    print(f"  [FAIL] Release notes — docs/releases/ not found")
    return False


def run_direct_checks() -> int:
    """Run all health checks directly."""
    print("=" * 56)
    from version import get_version
    print(f"  Novel Forge — Health Check {get_version()}")
    print("  Project:", str(PROJECT_ROOT))
    print("=" * 56)
    print()

    checks = [
        ("Python version",       check_python_version,     "critical"),
        ("Dependencies",         check_dependencies,        "critical"),
        ("Config",               check_config,              "critical"),
        ("SQLite connected",     check_sqlite,              "critical"),
        ("FTS5",                 check_fts5,                "warning"),
        ("Voice packs",          check_voice_packs,         "warning"),
        ("Meme packs",           check_meme_packs,          "warning"),
        ("Demo project",         check_demo_project,        "warning"),
        ("Guard registry",       check_guard_registry,      "warning"),
        ("Reports dir",          check_reports_dir,         "warning"),
        ("README version",       check_readme_version,      "warning"),
        ("Release notes",        check_release_notes,       "warning"),
    ]

    results = {}
    for name, fn, category in checks:
        try:
            ok = fn()
        except Exception as e:
            print(f"  [FAIL] {name} — exception: {e}")
            ok = False
        results[name] = {"ok": ok, "category": category}

    print()
    print("-" * 56)

    ok_count = sum(1 for v in results.values() if v["ok"])
    total = len(results)

    critical_fails = [
        name for name, v in results.items()
        if v["category"] == "critical" and not v["ok"]
    ]
    warning_fails = [
        name for name, v in results.items()
        if v["category"] == "warning" and not v["ok"]
    ]

    if critical_fails:
        print(f"  STATUS: FAIL")
        print(f"  Critical failures: {', '.join(critical_fails)}")
        exit_code = 2
    elif warning_fails:
        print(f"  STATUS: WARNING ({ok_count}/{total} passed)")
        for name in warning_fails:
            print(f"    - {name}")
        exit_code = 1
    else:
        print(f"  STATUS: PASS ({ok_count}/{total})")
        exit_code = 0

    print("-" * 56)
    return exit_code


# ═══════════════════════════════════════════════════
# JSON output mode
# ═══════════════════════════════════════════════════

def run_json_checks() -> int:
    """Run checks and output JSON."""
    import importlib

    results = {}

    checks = [
        ("python_version", check_python_version),
        ("dependencies", check_dependencies),
        ("config", check_config),
        ("sqlite", check_sqlite),
        ("fts5", check_fts5),
        ("voice_packs", check_voice_packs),
        ("meme_packs", check_meme_packs),
        ("demo_project", check_demo_project),
        ("guard_registry", check_guard_registry),
        ("reports_dir", check_reports_dir),
        ("readme_version", check_readme_version),
        ("release_notes", check_release_notes),
    ]

    for name, fn in checks:
        try:
            ok = fn()
        except Exception as e:
            ok = False
        results[name] = ok

    ok_count = sum(1 for v in results.values() if v)
    total = len(results)
    critical_ok = all(results.get(c, True) for c in CRITICAL_CHECKS)

    if not critical_ok:
        status = "FAIL"
        exit_code = 2
    elif ok_count < total:
        status = "WARNING"
        exit_code = 1
    else:
        status = "PASS"
        exit_code = 0

    output = {
        "status": status,
        "passed": ok_count,
        "total": total,
        "checks": results,
        "project_root": str(PROJECT_ROOT),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return exit_code


# ═══════════════════════════════════════════════════
# Main entry
# ═══════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Health check for novel-pipeline-write-engine",
    )
    parser.add_argument(
        "--direct", action="store_true",
        help="Force direct implementation (skip src.cli.commands_status)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output results as JSON",
    )
    args = parser.parse_args()

    # JSON mode always uses direct checks
    if args.json:
        return run_json_checks()

    # Try thin wrapper first, unless --direct is specified
    if not args.direct:
        result = run_via_status_module()
        if result is not None:
            return result

    # Fallback: direct implementation
    return run_direct_checks()


if __name__ == "__main__":
    sys.exit(main())
