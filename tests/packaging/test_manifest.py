from __future__ import annotations

from packaging.manifest import build_manifest


def test_manifest_contains_reproducibility_fields_and_no_runtime_data():
    manifest = build_manifest(version="1.5.0", git_sha="abc123", target_os="linux", arch="x86_64", python_version="3.12")
    assert manifest["version"] == "1.5.0"
    assert manifest["git_sha"] == "abc123"
    assert manifest["target"]["os"] == "linux"
    assert manifest["target"]["arch"] == "x86_64"
    assert "database" not in str(manifest).lower()
    assert "api_key" not in str(manifest).lower()

