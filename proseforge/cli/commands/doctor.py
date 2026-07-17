from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from proseforge.runtime.paths import resolve_paths
from proseforge.runtime.profile import RuntimeProfile, capabilities_for
from version import get_version


def doctor_report(*, profile: RuntimeProfile | str | None = None, data_dir: str | Path | None = None) -> dict[str, Any]:
    """Return stable, redacted diagnostics for support and installers."""
    selected = RuntimeProfile(profile or os.getenv("PROSEFORGE_RUNTIME_PROFILE", RuntimeProfile.SERVER.value))
    env = dict(os.environ)
    if data_dir is not None:
        env["PROSEFORGE_DATA_DIR"] = str(data_dir)
    paths = resolve_paths(selected, env)
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    checks = {
        "data_dir": paths.data_dir.is_dir(),
        "data_writable": os.access(paths.data_dir, os.W_OK),
        "backup_dir": paths.backup_dir.is_dir() or _can_create(paths.backup_dir),
        "database": paths.database_path is None or paths.database_path.exists() or paths.database_path.parent.is_dir(),
    }
    return {
        "status": "ok" if all(checks.values()) else "error",
        "checks": checks,
        "version": get_version(),
        "profile": selected.value,
        "database": capabilities_for(selected).database,
        "queue": capabilities_for(selected).queue,
        "backup_path": str(paths.backup_dir),
    }


def _can_create(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False
