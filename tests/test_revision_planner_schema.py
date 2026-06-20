"""revision_planner schema tests."""

from src.revision_planner.schema import (
    Finding,
    Severity,
    TextSpan,
    locate_in_text,
    normalize_severity,
)


def test_severity_aliases_warn_variants():
    assert normalize_severity("WARN") == Severity.WARNING
    assert normalize_severity("warn") == Severity.WARNING
    assert normalize_severity("WARNING") == Severity.WARNING
    assert normalize_severity("warning") == Severity.WARNING


def test_severity_aliases_error_variants():
    assert normalize_severity("FAIL") == Severity.ERROR
    assert normalize_severity("ERROR") == Severity.ERROR
    assert normalize_severity("critical") == Severity.ERROR


def test_severity_aliases_info_variants():
    assert normalize_severity("INFO") == Severity.INFO
    assert normalize_severity("info") == Severity.INFO


def test_severity_unknown_returns_default():
    assert normalize_severity("xyz") == Severity.WARNING
    assert normalize_severity("xyz", default=Severity.INFO) == Severity.INFO
    assert normalize_severity("") == Severity.WARNING


def test_textspan_predicates():
    full = TextSpan(paragraph_idx=2, char_start=100, char_end=120)
    assert full.has_offset() is True
    assert full.has_paragraph() is True

    only_para = TextSpan(paragraph_idx=2)
    assert only_para.has_offset() is False
    assert only_para.has_paragraph() is True

    empty = TextSpan()
    assert empty.has_offset() is False
    assert empty.has_paragraph() is False


def test_locate_in_text_exact_match():
    text = "第一段。\n\n第二段含证据词组。\n\n第三段。"
    span = locate_in_text(text, "证据词组")
    assert span is not None
    assert span.paragraph_idx == 1
    assert span.has_offset()
    assert text[span.char_start:span.char_end] == "证据词组"


def test_locate_in_text_no_match_returns_none():
    assert locate_in_text("abc", "xyz") is None


def test_locate_in_text_truncated_fallback():
    text = "第一段。\n\n第二段是这样写的，含有关键信息。\n\n第三段。"
    span = locate_in_text(text, "第二段是这样写的……（注释）")
    assert span is not None
    assert span.paragraph_idx == 1


def test_locate_in_text_empty_evidence():
    assert locate_in_text("text", "") is None
    assert locate_in_text("", "text") is None


def test_finding_to_dict_full():
    finding = Finding(
        source="prose_agent",
        code="NA_YI_KE",
        severity=Severity.WARNING,
        message="AI套话",
        evidence="那一刻，他终于",
        location=TextSpan(paragraph_idx=2, char_start=50, char_end=58),
        suggestion="替换为具体行动",
        metric=0.8,
    )
    payload = finding.to_dict()
    assert payload["source"] == "prose_agent"
    assert payload["code"] == "NA_YI_KE"
    assert payload["severity"] == "warning"
    assert payload["location"] == {
        "paragraph_idx": 2,
        "sentence_idx": None,
        "char_start": 50,
        "char_end": 58,
    }
    assert payload["metric"] == 0.8


def test_finding_to_dict_minimal():
    finding = Finding(
        source="rhythm_guard",
        code="UNIFORM_SENTENCE_LENGTH",
        severity=Severity.INFO,
        message="句长过稳",
    )
    payload = finding.to_dict()
    assert payload["location"] is None
    assert payload["evidence"] == ""
    assert payload["suggestion"] == ""
    assert payload["metric"] is None


def test_finding_raw_preserved():
    raw = {"native_field": "value", "extra": 123}
    finding = Finding(
        source="x",
        code="Y",
        severity=Severity.WARNING,
        message="m",
        raw=raw,
    )
    assert finding.raw == raw
