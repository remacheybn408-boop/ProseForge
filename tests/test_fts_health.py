from __future__ import annotations

from pathlib import Path

import pytest

from src.utils.fts_health import check_fts_health, ensure_fts_healthy, _safe_ident


# ── CODE_REVIEW #16: 动态 SQL 标识符护栏 ──
def test_safe_ident_accepts_valid_table_and_column_names():
    assert _safe_ident("novel_chapter_fts") == "novel_chapter_fts"
    assert _safe_ident("content") == "content"
    assert _safe_ident("content, title") == "content, title"   # 逗号分隔列


@pytest.mark.parametrize("bad", [
    "x; DROP TABLE chapters",
    "a b",
    "tbl)",
    "1table",
    "",
    "content,",
])
def test_safe_ident_rejects_injection_like(bad):
    with pytest.raises(ValueError):
        _safe_ident(bad)


def test_check_fts_health_reports_healthy_state(tmp_db: Path):
    result = check_fts_health({"db_path": str(tmp_db)})
    assert result["status"] == "healthy"
    assert result["ok"] is True
    assert "total_tables" in result
    assert isinstance(result["progress"], list)


def test_ensure_fts_healthy_reports_structured_noop(tmp_db: Path):
    result = ensure_fts_healthy({"db_path": str(tmp_db)})
    assert result["action"] == "none"
    assert result["health_before"]["status"] == "healthy"
    assert result["repair"]["status"] == "not_needed"
    assert isinstance(result["repair"]["progress"], list)


def test_ensure_fts_healthy_reports_missing_db(tmp_path: Path):
    missing_db = tmp_path / "missing.db"
    result = ensure_fts_healthy({"db_path": str(missing_db)})
    assert result["action"] == "repair_failed"
    assert result["health_before"]["status"] == "db_missing"
    assert result["repair"]["status"] == "db_missing"
    assert result["health_after"]["status"] == "db_missing"
