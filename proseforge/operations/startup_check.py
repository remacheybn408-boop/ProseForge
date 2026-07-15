from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class StartupReport:
    ready: bool
    checks: dict[str, str]


def run_startup_check(blob_root: str, backup_root: str) -> StartupReport:
    checks: dict[str, str] = {}
    for name, value in (("blob_root", blob_root), ("backup_root", backup_root)):
        path = Path(value)
        try:
            path.mkdir(parents=True, exist_ok=True)
            checks[name] = "ok" if path.is_dir() else "error"
        except OSError:
            checks[name] = "error"
    blob_path = Path(blob_root)
    probe = blob_path / f".healthcheck-{uuid4().hex}"
    try:
        probe.write_bytes(b"proseforge-healthcheck")
        checks["blob_roundtrip"] = "ok" if probe.read_bytes() == b"proseforge-healthcheck" else "error"
    except OSError:
        checks["blob_roundtrip"] = "error"
    finally:
        probe.unlink(missing_ok=True)
    return StartupReport(all(value == "ok" for value in checks.values()), checks)
