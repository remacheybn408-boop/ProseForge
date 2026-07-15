from proseforge.application.workflows.novel_workflow_service import NovelWorkflowService


async def run_novel(service: NovelWorkflowService, chapters: list[int]):
    return await service.run(chapters)
