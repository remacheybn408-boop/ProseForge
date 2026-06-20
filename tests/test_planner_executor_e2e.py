"""planner + executor tests and prose-agent end-to-end loop."""

from src.revision_planner.action import Action, OP_DELETE, OP_REPLACE
from src.revision_planner.executor import execute
from src.revision_planner.planner import PHRASE_REPLACEMENTS, plan
from src.revision_planner.schema import Finding, Severity, TextSpan


def test_plan_replaces_fixed_phrase():
    text = "他面对那场风暴。沉默了几秒。然后转身离开。"
    span = TextSpan(paragraph_idx=0, char_start=8, char_end=13)
    finding = Finding(
        source="prose_agent",
        code="CHEN_MO_JI_MIAO",
        severity=Severity.WARNING,
        message="AI套话 [CHEN_MO_JI_MIAO]: '沉默了几秒'",
        evidence="沉默了几秒",
        location=span,
    )
    actions = plan([finding], text)
    assert len(actions) == 1
    action = actions[0]
    assert action.op == OP_REPLACE
    assert action.args["original"] == "沉默了几秒"
    assert action.args["replacement"] in PHRASE_REPLACEMENTS["CHEN_MO_JI_MIAO"]
    assert "CHEN_MO_JI_MIAO" in action.source_findings


def test_plan_skips_non_actionable():
    span = TextSpan(paragraph_idx=0, char_start=0, char_end=4)
    findings = [
        Finding(
            source="prose_agent",
            code="AI_CLICHE_OVERFLOW",
            severity=Severity.WARNING,
            message="AI套话过多: 6处",
            evidence="",
            location=None,
        ),
        Finding(
            source="prose_agent",
            code="UNKNOWN",
            severity=Severity.WARNING,
            message="??",
            location=span,
        ),
    ]
    assert plan(findings, "测试文本") == []


def test_plan_skips_finding_without_location():
    finding = Finding(
        source="prose_agent",
        code="CHEN_MO_JI_MIAO",
        severity=Severity.WARNING,
        message="m",
        evidence="沉默了几秒",
        location=None,
    )
    assert plan([finding], "沉默了几秒") == []


def test_plan_dedupes_overlapping_spans():
    text = "他面对那场风暴。沉默了几秒。然后转身离开。"
    span = TextSpan(paragraph_idx=0, char_start=8, char_end=13)
    findings = [
        Finding(source="prose_agent", code="CHEN_MO_JI_MIAO", severity=Severity.WARNING, message="m1", evidence="沉默了几秒", location=span),
        Finding(source="prose_agent", code="CHEN_MO_JI_MIAO", severity=Severity.WARNING, message="m2", evidence="沉默了几秒", location=span),
    ]
    assert len(plan(findings, text)) == 1


def test_plan_skips_when_text_drifted():
    text = "他面对那场风暴。某段完全不同的话。然后转身离开。"
    bad_span = TextSpan(paragraph_idx=0, char_start=8, char_end=13)
    finding = Finding(
        source="prose_agent",
        code="CHEN_MO_JI_MIAO",
        severity=Severity.WARNING,
        message="m",
        evidence="沉默了几秒",
        location=bad_span,
    )
    assert plan([finding], text) == []


def test_plan_actions_sorted_descending_by_offset():
    text = "深吸一口气，他面对那场风暴。沉默了几秒。然后转身离开。"
    findings = [
        Finding(
            source="prose_agent",
            code="SHEN_XI_YI_KOU_QI",
            severity=Severity.WARNING,
            message="m",
            evidence="深吸一口气",
            location=TextSpan(paragraph_idx=0, char_start=0, char_end=5),
        ),
        Finding(
            source="prose_agent",
            code="CHEN_MO_JI_MIAO",
            severity=Severity.WARNING,
            message="m",
            evidence="沉默了几秒",
            location=TextSpan(paragraph_idx=0, char_start=14, char_end=19),
        ),
    ]
    actions = plan(findings, text)
    assert len(actions) == 2
    assert actions[0].location.char_start > actions[1].location.char_start


def test_plan_is_deterministic():
    text = "他面对那场风暴。沉默了几秒。然后转身离开。"
    span = TextSpan(paragraph_idx=0, char_start=8, char_end=13)
    finding = Finding(
        source="prose_agent",
        code="CHEN_MO_JI_MIAO",
        severity=Severity.WARNING,
        message="m",
        evidence="沉默了几秒",
        location=span,
    )
    first = plan([finding], text)
    second = plan([finding], text)
    assert first[0].args["replacement"] == second[0].args["replacement"]


def test_executor_applies_single_replace():
    text = "他面对那场风暴。沉默了几秒。然后转身离开。"
    action = Action(
        op=OP_REPLACE,
        location=TextSpan(char_start=8, char_end=13),
        args={"original": "沉默了几秒", "replacement": "顿了一顿"},
    )
    new_text, log = execute([action], text)
    assert "沉默了几秒" not in new_text
    assert "顿了一顿" in new_text
    assert log[0]["status"] == "applied"


def test_executor_applies_multiple_in_reverse_order():
    text = "深吸一口气，他面对风暴。沉默了几秒。然后离开。"
    actions = [
        Action(
            op=OP_REPLACE,
            location=TextSpan(char_start=0, char_end=5),
            args={"original": "深吸一口气", "replacement": "缓了缓"},
        ),
        Action(
            op=OP_REPLACE,
            location=TextSpan(char_start=12, char_end=17),
            args={"original": "沉默了几秒", "replacement": "顿了一顿"},
        ),
    ]
    new_text, log = execute(actions, text)
    assert "深吸一口气" not in new_text
    assert "沉默了几秒" not in new_text
    assert "缓了缓" in new_text
    assert "顿了一顿" in new_text
    assert all(entry["status"] == "applied" for entry in log)


def test_executor_skips_on_original_mismatch():
    text = "他完全不同的内容。"
    action = Action(
        op=OP_REPLACE,
        location=TextSpan(char_start=0, char_end=5),
        args={"original": "深吸一口气", "replacement": "缓了缓"},
    )
    new_text, log = execute([action], text)
    assert new_text == text
    assert log[0]["status"] == "skipped"
    assert "mismatch" in log[0]["reason"]


def test_executor_skips_invalid_span():
    text = "短文本。"
    action = Action(
        op=OP_REPLACE,
        location=TextSpan(char_start=100, char_end=200),
        args={"original": "x", "replacement": "y"},
    )
    new_text, log = execute([action], text)
    assert new_text == text
    assert log[0]["status"] == "skipped"


def test_executor_delete_op():
    text = "前缀。垃圾短语。后缀。"
    action = Action(
        op=OP_DELETE,
        location=TextSpan(char_start=3, char_end=8),
        args={"original": "垃圾短语。"},
    )
    new_text, log = execute([action], text)
    assert "垃圾短语" not in new_text
    assert log[0]["status"] == "applied"


SYNTHETIC_RICH = """林观澜推开洞府的门，阳光照进来。他深吸一口气，开始今天的修炼。
灵气在体内流转，一切如常。远处传来剑鸣声，他充耳不闻。
他突然意识到一件事，沉默了几秒。从未想过会是这样。
他又深吸一口气，看向远方。"""


def test_e2e_prose_agent_closes_the_loop():
    from src.agents.prose import ProseAgent
    from src.revision_planner.adapters.anti_ai import adapt

    agent = ProseAgent()
    raw_before = agent.review(SYNTHETIC_RICH, chapter_no=1)
    findings_before = adapt(raw_before, text=SYNTHETIC_RICH)

    actionable_codes = set(PHRASE_REPLACEMENTS.keys())
    actionable_before = [finding for finding in findings_before if finding.code in actionable_codes]
    assert actionable_before, "测试样本里必须包含 planner 能处理的 finding"

    actions = plan(findings_before, SYNTHETIC_RICH)
    assert actions, "planner 没产出任何 action"

    new_text, log = execute(actions, SYNTHETIC_RICH)
    assert new_text != SYNTHETIC_RICH
    assert sum(1 for entry in log if entry["status"] == "applied") > 0

    raw_after = agent.review(new_text, chapter_no=1)
    findings_after = adapt(raw_after, text=new_text)
    actionable_after = [finding for finding in findings_after if finding.code in actionable_codes]

    assert len(actionable_after) < len(actionable_before)
    for quote in ['"', "'", "“", "”"]:
        assert new_text.count(quote) <= SYNTHETIC_RICH.count(quote)
    assert new_text.count("——") <= SYNTHETIC_RICH.count("——")
