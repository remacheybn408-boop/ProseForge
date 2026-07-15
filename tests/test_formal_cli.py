import json
import shutil
from pathlib import Path

from src.interfaces.cli import main


def test_doctor_returns_machine_readable_health(tmp_path, capsys):
    code = main(["--project-root", str(tmp_path), "doctor"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["checks"]["schema"]["ok"] is False
    assert "project" in payload["checks"]
    assert "database" in payload["checks"]
    assert "rag" in payload["checks"]


def test_project_create_activates_and_persists_slug(tmp_path, capsys):
    (tmp_path / "database").mkdir()
    shutil.copy(Path(__file__).parents[1] / "database" / "schema.sql", tmp_path / "database" / "schema.sql")
    main(["--project-root", str(tmp_path), "project", "init"])
    capsys.readouterr()

    code = main([
        "--project-root", str(tmp_path), "project", "create",
        "--slug", "novel_alpha", "--title", "Alpha",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ok"
    assert payload["active_slot"] == "novel_alpha"
    project = json.loads(
        (tmp_path / "workspace" / "novel_alpha" / "project.json").read_text(
            encoding="utf-8"
        )
    )
    assert project["slug"] == "novel_alpha"


def test_chapter_pre_uses_active_project_defaults(tmp_path, capsys, monkeypatch):
    workspace = tmp_path / "workspace" / "novel_alpha"
    workspace.mkdir(parents=True)
    (tmp_path / "workspace" / "registry.json").write_text(
        json.dumps({"active_slot": "novel_alpha"}), encoding="utf-8"
    )
    (workspace / "project.json").write_text(
        json.dumps({"slug": "novel_alpha", "title": "Alpha"}), encoding="utf-8"
    )
    captured = {}

    def fake_run_pre(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "chapter_no": kwargs["chapter_no"]}

    import src.pipeline.pre as pre_module
    monkeypatch.setattr(pre_module, "run_pre", fake_run_pre)

    code = main(["--project-root", str(tmp_path), "chapter", "pre", "12"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "ok"
    assert captured["novel_slug"] == "novel_alpha"
    assert captured["novel_title"] == "Alpha"
    assert captured["chapter_no"] == 12
