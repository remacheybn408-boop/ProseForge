from proseforge.application.agents.artifact_store import create_artifact, verify_artifact
from proseforge.application.agents.scoped_memory import Memory, ScopedMemory

def test_artifact_checksum_and_scoped_memory():
    artifact = create_artifact("a", "report", {"score": 1}); assert verify_artifact(artifact)
    memory = ScopedMemory(); memory.put(Memory("run:r", "fact", "value", "a")); assert len(memory.active_for("run:r")) == 1; assert memory.active_for("run:other") == []
