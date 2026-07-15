import pytest

from proseforge.domain.ports.model_provider import GenerationEvent
from proseforge.workflows.novel_generation import generate_chapter_content


class Writer:
    def __init__(self):
        self.request = None

    async def stream(self, request):
        self.request = request
        yield GenerationEvent("content.delta", "A ")
        yield GenerationEvent("content.delta", "chapter.")


@pytest.mark.asyncio
async def test_writer_stream_is_collected_without_empty_success():
    provider = Writer()
    result = await generate_chapter_content(provider, model="writer-model", project_title="Book", chapter_title="Opening")

    assert result == "A chapter."
    assert provider.request.metadata["role"] == "writer"


@pytest.mark.asyncio
async def test_empty_writer_stream_is_rejected():
    class Empty:
        async def stream(self, request):
            if False:
                yield GenerationEvent("content.delta", "")

    with pytest.raises(ValueError, match="empty chapter"):
        await generate_chapter_content(Empty(), model="writer-model", project_title="Book", chapter_title="Opening")
