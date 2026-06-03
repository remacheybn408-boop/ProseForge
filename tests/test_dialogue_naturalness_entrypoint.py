"""test_dialogue_naturalness_entrypoint.py — 确认 dialogue_naturalness_guard 入口存在"""


def test_dialogue_naturalness_entrypoint_exists():
    """dialogue_naturalness_guard must have run_dialogue_naturalness_check."""
    from src.guards.dialogue_naturalness_guard import run_dialogue_naturalness_check
    assert callable(run_dialogue_naturalness_check)


def test_dialogue_naturalness_check_runs():
    """run_dialogue_naturalness_check must return valid dict without crash."""
    from src.guards.dialogue_naturalness_guard import run_dialogue_naturalness_check
    content = "\"你来了。\"他说。\n\"嗯。\"她低下头。\n\"路上还好吗？\""
    report = run_dialogue_naturalness_check(content, chapter_no=1)
    assert isinstance(report, dict)
    assert "status" in report
    assert report["status"] in ("PASS", "WARNING")
