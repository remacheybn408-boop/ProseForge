from proseforge.application.agents.evaluation import evaluate_candidate

def test_evaluation_is_reproducible_and_rejects_missing_evidence():
    result = evaluate_candidate({"score": 0.8}, ("score", "evidence")); assert result["status"] == "UNSUPPORTED"; assert result["fixture_hash"]
