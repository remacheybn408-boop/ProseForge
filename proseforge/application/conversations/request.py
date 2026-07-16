from __future__ import annotations

from collections.abc import Iterable

from proseforge.domain.ports.model_provider import GenerationRequest


def build_chat_request(
    *,
    model: str,
    messages: Iterable[object],
    excluded_message_id: str | None = None,
    context_text: str = "",
) -> GenerationRequest:
    system_text = "You are the ProseForge writing companion. Preserve the project's established facts and continuity."
    if context_text.strip():
        system_text += f"\nProject story memory:\n{context_text.strip()}"
    blocks: list[dict[str, object]] = []
    for message in messages:
        if excluded_message_id and getattr(message, "id", None) == excluded_message_id:
            continue
        role = str(getattr(message, "role", ""))
        content = str(getattr(message, "content", ""))
        if role not in {"user", "assistant"} or not content.strip():
            continue
        blocks.append({"role": role, "text": content})
    return GenerationRequest(
        model=model,
        system_blocks=({"role": "system", "text": system_text},),
        input_blocks=tuple(blocks),
        metadata={"workflow": "chat", "role": "companion"},
    )
