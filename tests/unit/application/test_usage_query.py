from types import SimpleNamespace

from proseforge.application.usage.query_usage import aggregate_usage


def test_usage_summary_keeps_actual_and_estimated_buckets_separate():
    result = aggregate_usage([
        SimpleNamespace(usage_source="provider", input_tokens=4, output_tokens=3, cached_input_tokens=0, reasoning_tokens=0, total_tokens=7, cost_usd=None),
        SimpleNamespace(usage_source="estimated", input_tokens=2, output_tokens=1, cached_input_tokens=0, reasoning_tokens=0, total_tokens=3, cost_usd=None),
    ])

    assert result["actual"]["total_tokens"] == 7
    assert result["estimated"]["total_tokens"] == 3
    assert result["actual"]["cost_usd"] is None
