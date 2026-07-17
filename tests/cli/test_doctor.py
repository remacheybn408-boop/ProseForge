from __future__ import annotations

import json

from proseforge.cli.commands.doctor import doctor_report
from proseforge.cli.main import main


def test_doctor_report_is_redacted_and_stable(tmp_path):
    report = doctor_report(profile="native", data_dir=tmp_path / "data")
    assert set(report) == {"status", "checks", "version", "profile", "database", "queue", "backup_path"}
    assert report["profile"] == "native"
    assert report["database"] == "sqlite"
    assert "secret" not in json.dumps(report).lower()


def test_doctor_json_cli(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("PROSEFORGE_RUNTIME_PROFILE", "native")
    assert main(["doctor", "--json", "--data-dir", str(tmp_path / "data")]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "ok"


def test_backup_create_json_cli(tmp_path, capsys):
    source = tmp_path / "data"
    source.mkdir()
    (source / "chapter.txt").write_text("chapter", encoding="utf-8")
    output = tmp_path / "backup.tar.gz"
    assert main(["backup", "create", "--source", str(source), "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert output.is_file()
    assert result["files"] == 1
