from __future__ import annotations
import hashlib, json
from dataclasses import dataclass

@dataclass(frozen=True)
class Artifact:
    id: str
    artifact_type: str
    payload: dict[str, object]
    sha256: str
    visibility: str = "run"

def create_artifact(artifact_id: str, artifact_type: str, payload: dict[str, object], visibility: str = "run") -> Artifact:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return Artifact(artifact_id, artifact_type, payload, hashlib.sha256(raw).hexdigest(), visibility)

def verify_artifact(artifact: Artifact) -> bool:
    raw = json.dumps(artifact.payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest() == artifact.sha256
