"""test_dialogue_structure_entrypoint.py — 确认 dialogue_structure_guard 入口存在

历史: 由 test_dialogue_naturalness_entrypoint.py 重命名而来（v0.7.3 拆分）。
"""


def test_dialogue_structure_entrypoint_exists():
    """dialogue_structure_guard must have run_dialogue_structure_check."""
    from src.guards.dialogue_structure_guard import run_dialogue_structure_check
    assert callable(run_dialogue_structure_check)


def test_dialogue_structure_check_runs():
    """run_dialogue_structure_check must return valid dict without crash."""
    from src.guards.dialogue_structure_guard import run_dialogue_structure_check
    content = "\"你来了。\"他说。\n\"嗯。\"她低下头。\n\"路上还好吗？\""
    report = run_dialogue_structure_check(content, chapter_no=1)
    assert isinstance(report, dict)
    assert "status" in report
    assert report["status"] in ("PASS", "WARNING")
