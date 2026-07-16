from dataclasses import dataclass

from proseforge.application.conversations.project_context import build_project_context


@dataclass
class ContextItem:
    id: str
    source_type: str
    source_id: str
    content: str
    pinned: bool = False
    priority: int = 0
    excluded: bool = False


@dataclass
class Chapter:
    id: str
    chapter_no: int
    title: str


def test_chat_context_includes_active_novel_chapter_content():
    result = build_project_context(
        context_items=[],
        active_chapters=[(Chapter("chapter-1", 1, "The Crossing"), "Mira crossed the river at dawn.")],
        input_budget=256,
    )

    assert "Mira crossed the river at dawn." in result
    assert "Chapter 1: The Crossing" in result
