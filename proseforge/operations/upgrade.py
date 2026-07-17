from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from proseforge.operations.backup import BackupService


class UpgradeBusyError(RuntimeError):
    """Another native process owns the upgrade lock."""


def run_upgrade(*, data_dir: str | Path, backup_dir: str | Path, migrate: Callable[[], None], doctor: Callable[[], None] | None = None, start: Callable[[], None] | None = None) -> Path:
    data = Path(data_dir).resolve()
    data.mkdir(parents=True, exist_ok=True)
    lock = data / ".upgrade.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError as exc:
        raise UpgradeBusyError("another upgrade is already running") from exc
    try:
        handle.write("upgrade in progress\n")
        handle.close()
        backup = BackupService(backup_dir).create(data).archive
        try:
            migrate()
            if doctor:
                doctor()
            if start:
                start()
        except Exception:
            with tempfile.TemporaryDirectory(prefix="proseforge-rollback-") as staging:
                BackupService(backup_dir).restore(backup, staging)
                _restore_files(Path(staging), data)
            raise
        return Path(backup)
    finally:
        lock.unlink(missing_ok=True)


def _restore_files(source: Path, destination: Path) -> None:
    for item in source.iterdir():
        if item.name == ".upgrade.lock":
            continue
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def check_upgrade(*, data_dir: str | Path, backup_dir: str | Path) -> dict[str, object]:
    data = Path(data_dir)
    return {"status": "ready" if data.is_dir() and data.exists() else "blocked", "data_dir": str(data), "backup_dir": str(Path(backup_dir)), "migration": "pending"}
