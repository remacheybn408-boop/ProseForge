from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from proseforge.domain.ports.model_provider import GenerationRequest, ModelProvider


UsageHandler = Callable[[str, str, dict[str, object], bool], Awaitable[None]]


async def _report_usage(handler: UsageHandler | None, request: GenerationRequest, event) -> None:
    if handler is None:
        return
    if event.event == "usage.updated":
        await handler(request.metadata.get("role", "unknown"), request.model, event.data, False)
    elif event.event == "response.completed" and event.data.get("usage"):
        await handler(request.metadata.get("role", "unknown"), request.model, event.data, True)


async def generate_chapter_content(
    provider: ModelProvider,
    *,
    model: str,
    project_title: str,
    chapter_title: str,
    context_text: str = "",
    usage_handler: UsageHandler | None = None,
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
        await _report_usage(usage_handler, request, event)
        if event.event == "content.delta":
            parts.append(event.text)
    content = "".join(parts).strip()
    if not content:
        raise ValueError("writer provider returned empty chapter content")
    return content


REVIEW_SCHEMA = {
    "type": "object",
    "required": ["status", "summary", "issues", "preserve", "rewrite_scope"],
    "properties": {
        "status": {"type": "string", "enum": ["PASS", "WARN", "BLOCK"]},
        "summary": {"type": "string"},
        "issues": {"type": "array"},
        "preserve": {"type": "array"},
        "rewrite_scope": {"type": "array"},
    },
}


async def _collect(provider: ModelProvider, request: GenerationRequest, usage_handler: UsageHandler | None = None) -> str:
    parts: list[str] = []
    async for event in provider.stream(request):
        await _report_usage(usage_handler, request, event)
        if event.event == "content.delta":
            parts.append(event.text)
    return "".join(parts).strip()


async def review_chapter_content(provider: ModelProvider, *, model: str, content: str, usage_handler: UsageHandler | None = None) -> dict[str, object]:
    request = GenerationRequest(
        model=model,
        system_blocks=({"role": "system", "text": "You are the Editor profile. Return only valid JSON."},),
        input_blocks=({"role": "user", "text": f"Review this chapter and identify continuity, character, plot, prose, pacing, canon, and style issues.\n{content}"},),
        response_schema=REVIEW_SCHEMA,
        metadata={"workflow": "novel-generation", "role": "editor"},
    )
    raw = await _collect(provider, request, usage_handler)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("editor returned invalid review JSON") from exc
    if not isinstance(result, dict) or str(result.get("status", "")).upper() not in {"PASS", "WARN", "BLOCK"}:
        raise ValueError("editor returned invalid review status")
    return result


async def rewrite_chapter_content(provider: ModelProvider, *, model: str, content: str, review: dict[str, object], usage_handler: UsageHandler | None = None) -> str:
    request = GenerationRequest(
        model=model,
        system_blocks=({"role": "system", "text": "You are the Editor profile. Rewrite only what the review requires."},),
        input_blocks=({"role": "user", "text": f"Original chapter:\n{content}\nReview JSON:\n{json.dumps(review, ensure_ascii=False)}"},),
        metadata={"workflow": "novel-generation", "role": "rewriter"},
    )
    rewritten = await _collect(provider, request, usage_handler)
    if not rewritten:
        raise ValueError("editor returned empty rewrite")
    return rewritten


async def run_writer_editor_loop(provider: ModelProvider, *, writer_model: str, editor_model: str, project_title: str, chapter_title: str, context_text: str = "", max_rewrites: int = 2, usage_handler: UsageHandler | None = None) -> tuple[str, int, dict[str, object]]:
    content = await generate_chapter_content(provider, model=writer_model, project_title=project_title, chapter_title=chapter_title, context_text=context_text, usage_handler=usage_handler)
    for rounds in range(max_rewrites + 1):
        review = await review_chapter_content(provider, model=editor_model, content=content, usage_handler=usage_handler)
        status = str(review["status"]).upper()
        if status == "PASS":
            return content, rounds, review
        if rounds >= max_rewrites:
            raise ValueError("chapter blocked after maximum rewrite rounds")
        content = await rewrite_chapter_content(provider, model=editor_model, content=content, review=review, usage_handler=usage_handler)
    raise AssertionError("unreachable")
