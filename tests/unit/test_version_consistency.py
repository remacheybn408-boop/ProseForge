from __future__ import annotations

import json
import tomllib
from pathlib import Path

from proseforge.api.main import create_app
from proseforge.version import __version__


ROOT = Path(__file__).resolve().parents[2]


def test_release_version_is_consistent_across_runtime_surfaces():
    expected = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    web_package = json.loads((ROOT / "apps" / "web" / "package.json").read_text(encoding="utf-8"))

    assert expected == "1.1.0"
    assert __version__ == expected
    assert pyproject["project"]["version"] == expected
    assert web_package["version"] == expected
    assert create_app().version == expected
