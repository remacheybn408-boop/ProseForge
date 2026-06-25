from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _find_project_root() -> Path:
    for path in (PLUGIN_ROOT, *PLUGIN_ROOT.parents):
        if (
            (path / "src").is_dir()
            and (path / "database" / "schema.sql").is_file()
            and (path / "pyproject.toml").is_file()
        ):
            return path
    raise RuntimeError("cannot locate ProseForge project root")


def test_nf_pipeline_help_accepts_project_root_from_outside_repo(tmp_path: Path):
    project_root = _find_project_root()
    script = PLUGIN_ROOT / "scripts" / "nf_pipeline.py"

    result = subprocess.run(
        [sys.executable, str(script), "--project-root", str(project_root), "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "--project-root PROJECT_ROOT" in result.stdout


def test_nf_project_status_accepts_project_root_env_from_outside_repo(tmp_path: Path):
    project_root = _find_project_root()
    script = PLUGIN_ROOT / "scripts" / "nf_project.py"
    env = os.environ.copy()
    env["PROSEFORGE_PROJECT_ROOT"] = str(project_root)

    result = subprocess.run(
        [sys.executable, str(script), "--action", "status"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert '"status"' in result.stdout
