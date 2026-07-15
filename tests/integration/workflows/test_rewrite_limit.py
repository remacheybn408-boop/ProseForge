import pytest

from proseforge.application.quality.rule_quality_service import RuleQualityService
from proseforge.application.writing.chapter_service import ChapterService


@pytest.mark.asyncio
async def test_rewrite_loop_stops_at_limit():
    service = ChapterService(lambda *_: "draft", RuleQualityService({}), lambda *_: {"status": "WARN"}, lambda *_: "rewritten", max_rewrites=1)
    result = await service.generate(object())
    assert result.status == "BLOCK"
    assert result.rewrite_rounds == 1
