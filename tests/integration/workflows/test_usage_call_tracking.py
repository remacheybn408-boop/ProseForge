from proseforge.application.usage.call_tracker import UsageCallTracker


def test_usage_call_tracker_separates_repeated_model_calls_by_role():
    tracker = UsageCallTracker("workflow-1", "chapter-1")

    first_update = tracker.call_id("editor", final=False)
    first_final = tracker.call_id("editor", final=True)
    second_update = tracker.call_id("editor", final=False)
    rewrite_final = tracker.call_id("rewriter", final=True)

    assert first_update == first_final
    assert second_update != first_update
    assert rewrite_final not in {first_update, second_update}
