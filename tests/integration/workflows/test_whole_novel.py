import pytest

from proseforge.application.workflows.novel_workflow_service import NovelWorkflowService


@pytest.mark.asyncio
async def test_pause_resume_does_not_regenerate_completed_chapters():
    calls = []

    async def runner(chapter_no):
        calls.append(chapter_no)
        return "PASS"

    service = NovelWorkflowService(runner)
    service.pause(after_current=True)
    first = await service.run([1, 2, 3])
    assert first.status == "PAUSED"
    service.resume()
    second = await service.run([1, 2, 3])
    assert second.status == "COMPLETED"
    assert calls == [1, 2, 3]
