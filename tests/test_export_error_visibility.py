import sqlite3

import pytest

from src.pipeline.export_novel import ExportDataError, get_chapters, get_novel_info


def test_export_novel_lookup_failure_is_not_treated_as_missing_novel():
    class BrokenConnection:
        def execute(self, *args, **kwargs):
            raise sqlite3.DatabaseError("database is malformed")

    with pytest.raises(ExportDataError, match="novel lookup"):
        get_novel_info(BrokenConnection(), "demo")


def test_export_chapter_query_failure_is_not_treated_as_empty_export():
    class BrokenConnection:
        def execute(self, *args, **kwargs):
            raise sqlite3.DatabaseError("database is malformed")

    with pytest.raises(ExportDataError, match="chapter query"):
        get_chapters(BrokenConnection(), 1)
