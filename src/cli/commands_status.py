#!/usr/bin/env python3
"""
commands_status.py — Health check for novel-pipeline-write-engine v0.5.0

Checks:
  1. Python >= 3.10
  2. config.json or config.example.json exists
  3. SQLite DB connectable
  4. FTS5 available
  5. Guard registry loads
  6. voice_packs/ directory exists
  7. templates/ directory exists
  8. reports/ directory writable
  9. README version matches expected
  10. Summary

Output: clean terminal text with [OK] [WARN] [MISS] markers. Exit code 0.
"""

import sys
from version import get_version
import json
import os
import sqlite3
import re
from pathlib import Path


from version import get_version as _gv; EXPECTED_VERSION = _gv()  # This is what we are building toward
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _icon(ok: bool) -> str:
    return "[OK]" if ok else "[WARN]"


def _miss_icon(ok: bool) -> str:
    return "[OK]" if ok else "[MISS]"


def check_python_version() -> bool:
    """Python >= 3.10"""
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 10)
    print(f"  {_icon(ok)} Python {major}.{minor} (need >= 3.10)")
    return ok


def check_config() -> bool:
    """config.json or config.example.json exists"""
    candidates = [
        PROJECT_ROOT / "config.json",
        PROJECT_ROOT / "config.example.json",
    ]
    for c in candidates:
        if c.exists():
            print(f"  {_icon(True)} Config found: {c.name}")
            return True
    print(f"  {_icon(False)} No config.json or config.example.json found")
    return False


def _load_config_path() -> str | None:
    """Find config.json path."""
    cfg = PROJECT_ROOT / "config.json"
    if cfg.exists():
        return str(cfg)
    cfg = PROJECT_ROOT / "config.example.json"
    if cfg.exists():
        return str(cfg)
    return None


def _get_db_path() -> str | None:
    """Extract db_path from config."""
    cfg_path = _load_config_path()
    if not cfg_path:
        return None
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("db_path")
    except Exception:
        return None


def check_sqlite_connectable() -> bool:
    """SQLite DB connectable"""
    db_path = _get_db_path()
    if not db_path:
        print(f"  {_icon(False)} Cannot determine DB path from config")
        return False
    if not Path(db_path).exists():
        print(f"  {_icon(False)} DB file not found: {db_path}")
        return False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.execute("SELECT 1")
        conn.close()
        print(f"  {_icon(True)} SQLite DB connectable: {db_path}")
        return True
    except Exception as e:
        print(f"  {_icon(False)} SQLite DB error: {e}")
        return False


def check_fts5() -> bool:
    """FTS5 available in SQLite"""
    db_path = _get_db_path()
    if not db_path or not Path(db_path).exists():
        print(f"  {_icon(False)} FTS5: cannot check (no DB)")
        return False
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name LIKE '%fts%'")
        rows = cur.fetchall()
        conn.close()
        if rows:
            count = len(rows)
            print(f"  {_icon(True)} FTS5 available ({count} virtual table(s))")
            return True
        else:
            print(f"  {_icon(False)} FTS5: no virtual tables found")
            return False
    except Exception as e:
        print(f"  {_icon(False)} FTS5 check error: {e}")
        return False


def check_guard_registry() -> bool:
    """Guard registry imports and validates"""
    scripts_dir = PROJECT_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        from guard_registry import GUARD_LEVELS, MODE_GUARDS
        guard_count = len(GUARD_LEVELS)
        mode_count = len(MODE_GUARDS)
        print(f"  {_icon(True)} Guard registry: {guard_count} guards, {mode_count} modes")
        return True
    except Exception as e:
        print(f"  {_icon(False)} Guard registry: {e}")
        return False


def check_voice_packs() -> bool:
    """voice_packs/ directory exists and has content"""
    vp = PROJECT_ROOT / "voice_packs"
    if vp.exists() and vp.is_dir():
        children = list(vp.iterdir())
        if children:
            print(f"  {_icon(True)} voice_packs/ exists ({len(children)} entries)")
            return True
        else:
            print(f"  {_icon(True)} voice_packs/ exists (empty)")
            return True
    else:
        print(f"  {_miss_icon(False)} voice_packs/ not found")
        return False


def check_templates() -> bool:
    """templates/ directory exists"""
    tmpl = PROJECT_ROOT / "templates"
    if tmpl.exists() and tmpl.is_dir():
        print(f"  {_icon(True)} templates/ exists")
        return True
    else:
        print(f"  {_miss_icon(False)} templates/ not found")
        return False


def check_reports_writable() -> bool:
    """reports/ directory writable"""
    rpt = PROJECT_ROOT / "reports"
    if not rpt.exists():
        try:
            rpt.mkdir(parents=True, exist_ok=True)
            print(f"  {_icon(True)} reports/ created and writable")
            return True
        except Exception as e:
            print(f"  {_icon(False)} reports/ cannot create: {e}")
            return False
    # Test write
    test_file = rpt / ".status_test"
    try:
        test_file.write_text("test", encoding="utf-8")
        test_file.unlink()
        print(f"  {_icon(True)} reports/ writable")
        return True
    except Exception as e:
        print(f"  {_icon(False)} reports/ not writable: {e}")
        return False


def check_readme_version() -> bool:
    """README version matches expected"""
    readme = PROJECT_ROOT / "README.md"
    if not readme.exists():
        print(f"  {_icon(False)} README.md not found")
        return False
    try:
        content = readme.read_text(encoding="utf-8")
        # Look for version pattern like "v0.4.5" or "v0.5.0" in first line
        first_line = content.split("\n")[0]
        version_match = re.search(r'v\d+\.\d+\.\d+', first_line)
        if version_match:
            found = version_match.group(0)
            match_ok = found == EXPECTED_VERSION
            icon = _icon(match_ok) if match_ok else _icon(False)
            tag = "(match)" if match_ok else f"(expected {EXPECTED_VERSION})"
            print(f"  {icon} README version: {found} {tag}")
            return match_ok
        else:
            print(f"  {_icon(False)} README: no version found in title")
            return False
    except Exception as e:
        print(f"  {_icon(False)} README check error: {e}")
        return False


def main() -> int:
    print("=" * 56)
    print(f"  Novel Forge — Health Check {get_version()}")
    print("  Project:", str(PROJECT_ROOT))
    print("=" * 56)
    print()

    results = {
        "python_version": check_python_version(),
        "config": check_config(),
        "sqlite_db": check_sqlite_connectable(),
        "fts5": check_fts5(),
        "guard_registry": check_guard_registry(),
        "voice_packs": check_voice_packs(),
        "templates": check_templates(),
        "reports_writable": check_reports_writable(),
        "readme_version": check_readme_version(),
    }

    print()
    print("-" * 56)

    ok_count = sum(1 for v in results.values() if v)
    total = len(results)
    if ok_count == total:
        print(f"  Result: ALL PASS ({ok_count}/{total})")
    else:
        print(f"  Result: {ok_count}/{total} checks passed")
        for name, passed in results.items():
            if not passed:
                print(f"    - {name}: WARN")

    print("-" * 56)

    # Always exit 0 for status (warnings are not errors)
    return 0


if __name__ == "__main__":
    sys.exit(main())
