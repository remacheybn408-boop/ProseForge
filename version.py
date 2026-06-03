#!/usr/bin/env python3
"""version.py — Single source of truth for engine version."""
from pathlib import Path

_VFILE = Path(__file__).resolve().parent / "VERSION"
_FALLBACK = "v0.6.5"


def get_version() -> str:
    """Read VERSION file, fall back if missing."""
    try:
        return _VFILE.read_text(encoding="utf-8").strip()
    except Exception:
        return _FALLBACK


def get_version_tuple() -> tuple:
    """Return (major, minor, patch) ints for programmatic use."""
    import re
    v = get_version()
    m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", v)
    if m:
        return int(m[1]), int(m[2]), int(m[3])
    return (0, 0, 0)
