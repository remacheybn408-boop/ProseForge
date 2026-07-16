from proseforge.operations.startup_check import run_startup_check


def test_startup_check_creates_required_roots(tmp_path):
    report = run_startup_check(str(tmp_path / "blobs"), str(tmp_path / "backups"))
    assert report.ready
