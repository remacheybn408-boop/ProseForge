"""anti_ai adapter tests."""

from src.revision_planner.adapters.anti_ai import _extract_code, adapt
from src.revision_planner.schema import Severity


def test_extract_code_ai_cliche():
    assert _extract_code("AI套话 [NA_YI_KE]: '那一刻，他终于'") == "NA_YI_KE"


def test_extract_code_ai_sentence_pattern():
    assert _extract_code("AI句式 [NOT_A_ER_SHI]: '不是X而是Y'") == "NOT_A_ER_SHI"


def test_extract_code_hard_science():
    assert _extract_code("硬科普 [HARD_SCIENCE_TERM]: '量子'") == "HARD_SCIENCE_TERM"


def test_extract_code_synthetic_water_look():
    assert _extract_code("水文段落: 含3次'看了...一眼'") == "WATER_LOOK_REPEAT"


def test_extract_code_synthetic_say_repeat():
    assert _extract_code("对话标记重复: 2次'说了一句/道了一声'") == "WATER_SAY_REPEAT"


def test_extract_code_synthetic_summary():
    assert _extract_code("总结腔/说教腔: 2处") == "SUMMARY_TONE"


def test_extract_code_synthetic_cliche_overflow():
    assert _extract_code("AI套话过多: 6处") == "AI_CLICHE_OVERFLOW"


def test_extract_code_synthetic_not_a_b_overflow():
    assert _extract_code("AI句式泛滥: 本章共5处'不是而是'类") == "NOT_A_B_OVERFLOW"


def test_extract_code_unknown_message():
    assert _extract_code("一段不认识的消息") == "UNKNOWN"
    assert _extract_code("") == "UNKNOWN"


def test_adapt_basic_finding_with_evidence():
    text = "开头。\n\n中间有一句：那一刻，他终于明白命运。\n\n结尾。"
    agent_output = {
        "findings": [
            {
                "level": "WARN",
                "message": "AI套话 [NA_YI_KE]: '那一刻，他终于'",
                "evidence": "中间有一句：那一刻，他终于明白命运。结尾。",
                "suggestion": "替换为具体动作/感受描写",
            }
        ]
    }
    out = adapt(agent_output, text=text)
    assert len(out) == 1
    finding = out[0]
    assert finding.source == "prose_agent"
    assert finding.code == "NA_YI_KE"
    assert finding.severity == Severity.WARNING
    assert finding.evidence == "那一刻，他终于"
    assert finding.location is not None
    assert finding.location.paragraph_idx == 1
    assert finding.location.has_offset()
    assert text[finding.location.char_start:finding.location.char_end] == "那一刻，他终于"
    assert "_snippet" in finding.raw
    assert finding.suggestion.startswith("替换为")


def test_adapt_finding_without_evidence_has_no_location():
    agent_output = {
        "findings": [
            {
                "level": "WARN",
                "message": "AI套话过多: 6处",
                "evidence": "",
                "suggestion": "AI套话是编辑最敏感的标记",
            }
        ]
    }
    out = adapt(agent_output, text="任意文本")
    assert len(out) == 1
    assert out[0].code == "AI_CLICHE_OVERFLOW"
    assert out[0].location is None


def test_adapt_evidence_not_found_in_text():
    agent_output = {
        "findings": [
            {
                "level": "WARN",
                "message": "AI套话 [SHEN_XI_YI_KOU_QI]: '深吸一口气'",
                "evidence": "完全不在原文里的字符串zzzz",
                "suggestion": "",
            }
        ]
    }
    out = adapt(agent_output, text="他打开门走进去。")
    assert len(out) == 1
    assert out[0].location is None
    assert out[0].code == "SHEN_XI_YI_KOU_QI"


def test_adapt_preserves_raw():
    raw_finding = {
        "level": "WARN",
        "message": "AI套话 [CHEN_MO_JI_MIAO]: '沉默了几秒'",
        "evidence": "沉默了几秒",
        "suggestion": "",
        "custom_extra": "shouldn't be lost",
    }
    out = adapt({"findings": [raw_finding]}, text="沉默了几秒。")
    assert out[0].raw == raw_finding
    assert out[0].raw["custom_extra"] == "shouldn't be lost"


def test_adapt_empty_findings():
    assert adapt({"findings": []}, text="abc") == []
    assert adapt({}, text="abc") == []
    assert adapt({"findings": None}, text="abc") == []


def test_adapt_disambiguates_repeated_phrase():
    text = "他深吸一口气，走出门。\n\n他又深吸一口气，看向远方。\n\n第三次他深吸一口气。"
    agent_output = {
        "findings": [
            {
                "level": "WARN",
                "message": "AI套话 [SHEN_XI_YI_KOU_QI]: '深吸一口气'",
                "evidence": "他深吸一口气，走出门。",
                "suggestion": "",
            },
            {
                "level": "WARN",
                "message": "AI套话 [SHEN_XI_YI_KOU_QI]: '深吸一口气'",
                "evidence": "他又深吸一口气，看向远方。",
                "suggestion": "",
            },
            {
                "level": "WARN",
                "message": "AI套话 [SHEN_XI_YI_KOU_QI]: '深吸一口气'",
                "evidence": "第三次他深吸一口气。",
                "suggestion": "",
            },
        ]
    }
    out = adapt(agent_output, text=text)
    starts = [finding.location.char_start for finding in out if finding.location]
    assert len(out) == 3
    assert len(set(starts)) == 3
    assert starts == sorted(starts)


def test_adapt_severity_normalization():
    out = adapt(
        {"findings": [{"level": "WARN", "message": "AI套话 [X]: 'y'", "evidence": ""}]},
        text="",
    )
    assert out[0].severity == Severity.WARNING


SYNTHETIC = """林观澜推开洞府的门，阳光照进来。他深吸一口气，开始今天的修炼。
灵气在体内流转，一切如常。他突然意识到一件事。那一刻，他终于明白命运的玩笑。从未想过会是这样。沉默了几秒。心中涌起一阵复杂。这就是他的全部意义。他又深吸一口气。
不是境界不够，而是心境不到。
总而言之，他知道自己别无选择。综上所述，必须做出决定。"""


def test_integration_adapt_real_agent_output():
    from src.agents.prose import ProseAgent

    agent = ProseAgent()
    raw_output = agent.review(SYNTHETIC, chapter_no=1)
    findings = adapt(raw_output, text=SYNTHETIC)

    assert findings
    assert all(finding.source == "prose_agent" for finding in findings)
    assert all(finding.severity == Severity.WARNING for finding in findings)

    actionable = [finding for finding in findings if finding.code != "UNKNOWN"]
    codes = {finding.code for finding in actionable}
    assert "NA_YI_KE" in codes
    assert "SHEN_XI_YI_KOU_QI" in codes
    assert "CHEN_MO_JI_MIAO" in codes
    assert "AI_CLICHE_OVERFLOW" in codes or "SUMMARY_TONE" in codes

    with_evidence = [finding for finding in actionable if finding.evidence]
    located = [finding for finding in with_evidence if finding.location is not None]
    assert len(located) >= int(len(with_evidence) * 0.6)
