from __future__ import annotations

import pytest

from proseforge.operations.upgrade import UpgradeBusyError, run_upgrade


def test_upgrade_failure_restores_data_from_verified_backup(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    marker = data / "project.json"
    marker.write_text("before", encoding="utf-8")

    def migrate():
        marker.write_text("after", encoding="utf-8")
        raise RuntimeError("migration failed")

    with pytest.raises(RuntimeError, match="migration failed"):
        run_upgrade(data_dir=data, backup_dir=tmp_path / "backups", migrate=migrate)
    assert marker.read_text(encoding="utf-8") == "before"
    assert not (data / ".upgrade.lock").exists()


def test_upgrade_lock_rejects_second_process(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    lock = data / ".upgrade.lock"
    lock.write_text("other", encoding="utf-8")
    with pytest.raises(UpgradeBusyError):
        run_upgrade(data_dir=data, backup_dir=tmp_path / "backups", migrate=lambda: None)
