from __future__ import annotations

from proseforge.operations.startup_check import run_startup_check


def test_startup_check_round_trips_blob_probe(tmp_path):
    report = run_startup_check(str(tmp_path / "blobs"), str(tmp_path / "backups"))

    assert report.ready is True
    assert report.checks["blob_roundtrip"] == "ok"
    assert not list((tmp_path / "blobs").glob(".healthcheck-*"))
