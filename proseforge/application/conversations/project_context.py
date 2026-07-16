from __future__ import annotations

from collections.abc import Iterable

from proseforge.context_engine.compiler import compile_context


def build_project_context(*, context_items: Iterable[object], active_chapters: Iterable[tuple[object, str]], input_budget: int) -> str:
    blocks: list[dict[str, object]] = []
    for item in context_items:
        if bool(getattr(item, "excluded", False)):
            continue
        blocks.append({
            "id": getattr(item, "id", ""),
            "source_type": getattr(item, "source_type", "memory"),
            "source_ids": [getattr(item, "source_id", getattr(item, "id", ""))],
            "content": getattr(item, "content", ""),
            "pinned": getattr(item, "pinned", False),
            "priority": getattr(item, "priority", 100),
        })
    for chapter, content in active_chapters:
        if not content.strip():
            continue
        chapter_id = str(getattr(chapter, "id", ""))
        chapter_no = getattr(chapter, "chapter_no", "")
        title = getattr(chapter, "title", "")
        blocks.append({
            "id": f"chapter:{chapter_id}",
            "source_type": "chapter",
            "source_ids": [chapter_id],
            "content": f"Chapter {chapter_no}: {title}\n{content}",
            "pinned": False,
            "priority": 10,
        })
    compiled = compile_context("chat", blocks, input_budget=max(1, input_budget))
    return "\n\n".join(str(block.get("content", "")) for block in compiled.blocks)
