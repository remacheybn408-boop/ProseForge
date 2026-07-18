from __future__ import annotations
import hashlib
import json

def fixture_hash(fixture: dict[str, object]) -> str: return hashlib.sha256(json.dumps(fixture, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def evaluate_candidate(candidate: dict[str, object], required: tuple[str, ...]) -> dict[str, object]:
    missing = [key for key in required if key not in candidate]
    return {"status": "UNSUPPORTED" if missing else "PASS", "missing": missing, "fixture_hash": fixture_hash(candidate)}
