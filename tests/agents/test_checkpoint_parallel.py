import asyncio
import pytest
from proseforge.application.agents.checkpoint import make_checkpoint
from proseforge.application.agents.parallel import bounded_parallel

@pytest.mark.asyncio
async def test_checkpoint_and_bounded_parallelism():
    checkpoint = make_checkpoint("r", "a", 2, ("artifact-1",)); active = 0; peak = 0
    async def task():
        nonlocal active, peak
        active += 1; peak = max(peak, active); await asyncio.sleep(0); active -= 1; return checkpoint.node_id
    assert await bounded_parallel([task, task, task], 2) == ["a", "a", "a"]
    assert peak <= 2
