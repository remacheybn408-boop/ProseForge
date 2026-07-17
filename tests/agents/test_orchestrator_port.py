import pytest
from proseforge.domain.agents.ports import AgentRunRequest
from proseforge.infrastructure.agents.factory import create_orchestrator

@pytest.mark.asyncio
async def test_local_orchestrator_is_idempotent_and_replays_events():
    orchestrator = create_orchestrator(); request = AgentRunRequest("r", "p", "hash", 1)
    first = await orchestrator.start(request); second = await orchestrator.start(request)
    assert first == second
    await orchestrator.pause("r")
    events = [event async for event in orchestrator.events("r", after=1)]
    assert events[-1].event == "run.paused"
