from __future__ import annotations

from proseforge.domain.ports.model_provider import GenerationRequest, ModelProvider


async def generate_chapter_content(
    provider: ModelProvider,
    *,
    model: str,
    project_title: str,
    chapter_title: str,
    context_text: str = "",
) -> str:
    """Collect one streamed Writer response without mutating persistence."""
    prompt = (
        f"Write a complete novel chapter titled {chapter_title!r} for the project {project_title!r}.\n"
        "Preserve continuity and do not include planning commentary.\n"
    )
    if context_text:
        prompt += f"Story context:\n{context_text}\n"
    request = GenerationRequest(
        model=model,
        system_blocks=({"role": "system", "text": "You are the Writer profile for ProseForge."},),
        input_blocks=({"role": "user", "text": prompt},),
        metadata={"workflow": "novel-generation", "role": "writer"},
    )
    parts: list[str] = []
    async for event in provider.stream(request):
        if event.event == "content.delta":
            parts.append(event.text)
    content = "".join(parts).strip()
    if not content:
        raise ValueError("writer provider returned empty chapter content")
    return content
