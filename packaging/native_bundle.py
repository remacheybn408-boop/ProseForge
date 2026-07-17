"""Build a reproducible native distribution bundle.

The OS-specific installers wrap this bundle.  The builder deliberately keeps
the staging tree free of runtime user data and emits a manifest containing
checksums for every shipped file.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import tarfile
import tempfile
import zipfile
from pathlib import Path

from packaging.manifest import build_manifest, hash_file, write_manifest


def _copy_tree(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def _write_launchers(root: Path, target: str) -> None:
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    (bin_dir / "proseforge").write_text(
        "#!/bin/sh\nexec python -m proseforge.cli.main \"$@\"\n",
        encoding="utf-8",
    )
    (bin_dir / "proseforge.cmd").write_text(
        "@echo off\r\npython -m proseforge.cli.main %*\r\n",
        encoding="utf-8",
    )
    if target in {"linux", "macos"}:
        (bin_dir / "proseforge").chmod(0o755)


def _file_hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)).replace("\\", "/"): hash_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    }


def build_bundle(*, project_root: Path, output_dir: Path, target: str, archive_format: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    revision = "unknown"
    try:
        import subprocess

        revision = subprocess.check_output(
            ["git", "-C", str(project_root), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        pass

    with tempfile.TemporaryDirectory(prefix="proseforge-native-") as temp:
        stage = Path(temp) / f"ProseForge-{target}"
        stage.mkdir()
        for name in ("proseforge", "src", "packaging", "VERSION", "pyproject.toml", "README.md"):
            source = project_root / name
            destination = stage / name
            if source.is_dir():
                _copy_tree(source, destination)
            elif source.is_file():
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
        frontend_dist = project_root / "apps" / "web" / "dist"
        if frontend_dist.is_dir():
            _copy_tree(frontend_dist, stage / "frontend-dist")
        else:
            _copy_tree(project_root / "apps" / "web" / "src", stage / "frontend-source")
        _write_launchers(stage, target)
        manifest = build_manifest(git_sha=revision, target_os=target)
        manifest["distribution"] = "native-source-bundle"
        manifest["files"] = _file_hashes(stage)
        write_manifest(stage / "manifest.json", manifest)

        suffix = ".zip" if archive_format == "zip" else ".tar.gz"
        archive = output_dir / f"ProseForge-{target}-{revision[:12]}{suffix}"
        if archive_format == "zip":
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(stage.rglob("*")):
                    if path.is_file():
                        bundle.write(path, path.relative_to(stage.parent))
        else:
            with tarfile.open(archive, "w:gz") as bundle:
                bundle.add(stage, arcname=stage.name)
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        (output_dir / f"{archive.name}.sha256").write_text(
            f"{checksum}  {archive.name}\n", encoding="utf-8"
        )
        (output_dir / "BUILD.txt").write_text(
            f"archive={archive.name}\nsha256={checksum}\ntarget={target}\n",
            encoding="utf-8",
        )
        shutil.copy2(stage / "manifest.json", output_dir / "manifest.json")
        return archive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--target", choices=("windows", "linux", "macos"), required=True)
    parser.add_argument("--format", choices=("zip", "tar.gz"), default="tar.gz")
    args = parser.parse_args()
    archive = build_bundle(
        project_root=args.root.resolve(),
        output_dir=args.output.resolve(),
        target=args.target,
        archive_format=args.format,
    )
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
