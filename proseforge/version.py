from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


def _load_version() -> str:
    try:
        return (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        try:
            return version("proseforge")
        except PackageNotFoundError:
            return "0.0.0+unknown"


__version__ = _load_version()
