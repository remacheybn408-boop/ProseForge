from pathlib import Path

from proseforge.infrastructure.legacy_engine.adapter import LegacyNovelEngineAdapter


def test_adapter_rejects_commit_without_pre_state(tmp_path: Path) -> None:
    staged_file = tmp_path / "chapter.txt"
    staged_file.write_text("draft", encoding="utf-8")
    adapter = LegacyNovelEngineAdapter(project_root=tmp_path)

    result = adapter.run_rule_quality(
        legacy_slot="book",
        novel_slug="book",
        novel_title="Book",
        volume_no=1,
        chapter_no=1,
        chapter_type="normal",
        staged_file=str(staged_file),
    )

    assert result.can_commit is False
    assert "pre_state" in " ".join(result.blocked_by)
