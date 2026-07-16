from types import SimpleNamespace

from proseforge.application.conversations.request import build_chat_request


def test_chat_request_contains_project_memory_and_visible_history():
    request = build_chat_request(
        model="writer-model",
        messages=[
            SimpleNamespace(id="u1", role="user", content="What happened at the harbor?"),
            SimpleNamespace(id="a1", role="assistant", content="The tide turned before dawn."),
        ],
        excluded_message_id="pending-assistant",
        context_text="Mira is afraid of deep water.",
    )

    assert "Mira is afraid of deep water." in request.system_blocks[0]["text"]
    assert [block["role"] for block in request.input_blocks] == ["user", "assistant"]
    assert request.input_blocks[1]["text"] == "The tide turned before dawn."
