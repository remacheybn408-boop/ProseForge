from proseforge.application.writing.chapter_service import ChapterService, ChapterGenerationResult


async def generate_chapter(service: ChapterService, request: object, context: dict | None = None) -> ChapterGenerationResult:
    return await service.generate(request, context)
