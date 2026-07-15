from src.pipeline.run_artifacts import create_run_artifacts


def test_each_operation_gets_a_unique_isolated_run_directory(tmp_path):
    first = create_run_artifacts(tmp_path, chapter_no=1, operation="post")
    second = create_run_artifacts(tmp_path, chapter_no=1, operation="post")

    assert first.run_id != second.run_id
    assert first.directory != second.directory
    assert first.directory.parent == tmp_path / "runs" / "post" / "chapter_001"
    assert second.directory.parent == tmp_path / "runs" / "post" / "chapter_001"
    assert first.directory.is_dir()
    assert second.directory.is_dir()
