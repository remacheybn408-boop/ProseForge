from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from .mapper import map_chapters, map_project
from .scanner import scan_workspace
from .sqlite_reader import read_legacy_slot


@dataclass(frozen=True)
class LegacyImportReport:
    status: str
    projects_imported: int
    chapters_imported: int
    hash_mismatches: tuple[str, ...] = ()
    failed_slots: tuple[str, ...] = ()


class LegacyImporter:
    def __init__(self, archive_root: str | Path = "/data/backups/legacy-import"):
        self.archive_root = Path(archive_root)

    async def import_workspace(self, workspace: str | Path) -> LegacyImportReport:
        imported_projects = imported_chapters = 0
        mismatches: list[str] = []
        failures: list[str] = []
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        for slot in scan_workspace(workspace):
            try:
                snapshot = read_legacy_slot(slot.root, slot.database)
                project = map_project(slot)
                map_chapters(project, snapshot)
                imported_projects += 1
                imported_chapters += len(snapshot.chapters)
                destination = self.archive_root / timestamp / slot.root.name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(slot.root, destination, dirs_exist_ok=True)
                for path in destination.rglob("*"):
                    if path.is_file():
                        path.chmod(0o444)
            except Exception:
                failures.append(slot.root.name)
        status = "COMPLETED" if not failures else ("PARTIAL" if imported_projects else "FAILED")
        return LegacyImportReport(status, imported_projects, imported_chapters, tuple(mismatches), tuple(failures))
