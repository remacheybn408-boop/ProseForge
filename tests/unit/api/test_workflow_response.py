import json
from types import SimpleNamespace

from proseforge.api.routes.workflows import _response


def test_workflow_response_exposes_durable_progress_and_budget_details():
    run = SimpleNamespace(
        id="run-1",
        project_id="project-1",
        workflow_type="NOVEL",
        status="RUNNING",
        estimated_cost=0.42,
        cost_limit=1.0,
        used_tokens=120,
        token_limit=1000,
        last_error=None,
        checkpoint=json.dumps(
            {
                "phase": "CHAPTER_2_DRAFTING",
                "command": {
                    "chapter_numbers": [1, 2, 3],
                    "model": "writer-model",
                    "editor_model": "editor-model",
                },
                "completed_steps": ["context", "chapter_1"],
                "completed_chapters": [1],
                "retry_count": 2,
            }
        ),
    )

    result = _response(run)

    assert result["current_step"] == "CHAPTER_2_DRAFTING"
    assert result["completed_steps"] == ["context", "chapter_1"]
    assert result["chapter_progress"] == {"current": 2, "completed": [1], "total": 3, "requested": [1, 2, 3]}
    assert result["retry_count"] == 2
    assert result["model"] == "writer-model"
    assert result["editor_model"] == "editor-model"
    assert result["token_cost_estimate"] == {"used_tokens": 120, "token_limit": 1000, "cost_usd": 0.42, "cost_limit": 1.0}
