from proseforge.domain.quality.analyzers.prose_analyzer import ProseAnalyzer


def test_prose_analyzer_returns_structured_result() -> None:
    result = ProseAnalyzer().review("他不禁倒吸一口凉气", chapter_no=1)
    assert isinstance(result, dict)
    assert "findings" in result
    assert result["chapter"] == 0
