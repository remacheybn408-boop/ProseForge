import pytest

from proseforge.application.quality.rule_quality_service import RuleQualityService
from proseforge.application.writing.chapter_service import ChapterService


@pytest.mark.asyncio
async def test_passed_chapter_is_committed_once():
    commits = []
    service = ChapterService(lambda *_: "draft", RuleQualityService({}), lambda *_: {"status": "PASS"}, lambda *_: "rewrite", lambda content, _: commits.append(content))
    result = await service.generate(object())
    assert result.status == "PASS"
    assert commits == ["draft"]
