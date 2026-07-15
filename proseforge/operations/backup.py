from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class BackupVerification:
    archive: str
    files: int
    sha256: str


class BackupService:
    def __init__(self, backup_root: str | Path):
        self.backup_root = Path(backup_root)

    def create(self, source_root: str | Path) -> BackupVerification:
        source = Path(source_root).resolve()
        if not source.is_dir():
            raise ValueError("backup source does not exist")
        self.backup_root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive = self.backup_root / f"proseforge-{stamp}.tar.gz"
        files = 0
        with tarfile.open(archive, "w:gz") as tar:
            for path in sorted(source.rglob("*")):
                if path.is_file() and not path.is_symlink():
                    tar.add(path, arcname=path.relative_to(source))
                    files += 1
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        manifest = archive.with_suffix(archive.suffix + ".json")
        manifest.write_text(json.dumps({"archive": archive.name, "files": files, "sha256": digest}), encoding="utf-8")
        return BackupVerification(str(archive), files, digest)

    def verify(self, archive: str | Path) -> BackupVerification:
        path = Path(archive)
        if not path.is_file() or path.suffixes[-2:] != [".tar", ".gz"]:
            raise ValueError("invalid backup archive")
        with tarfile.open(path, "r:gz") as tar:
            members = [member for member in tar.getmembers() if member.isfile()]
            if any(Path(member.name).is_absolute() or ".." in Path(member.name).parts for member in members):
                raise ValueError("backup contains unsafe path")
        return BackupVerification(str(path), len(members), hashlib.sha256(path.read_bytes()).hexdigest())

    def list(self) -> list[Path]:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        return sorted(self.backup_root.glob("proseforge-*.tar.gz"), reverse=True)

    def restore(self, archive: str | Path, destination: str | Path) -> BackupVerification:
        """Restore into a staging directory after validating every archive member."""
        verified = self.verify(archive)
        target = Path(destination).resolve()
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(verified.archive, "r:gz") as tar:
            for member in tar.getmembers():
                member_path = (target / member.name).resolve()
                if target != member_path and target not in member_path.parents:
                    raise ValueError("backup contains unsafe path")
            tar.extractall(target, filter="data")
        return verified
