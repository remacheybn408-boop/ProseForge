import json

import httpx
import pytest
import respx

from proseforge.domain.ports.model_provider import GenerationRequest
from proseforge.providers.openai import OpenAIProvider


@pytest.mark.asyncio
@respx.mock
async def test_openai_models_preserve_unknown_ids():
    respx.get("https://api.test/v1/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "future-model"}]}))
    models = await OpenAIProvider("secret", "https://api.test/v1").list_models()
    assert models[0].model_id == "future-model"


@pytest.mark.asyncio
@respx.mock
async def test_openai_response_stream_normalizes_events():
    body = "\n".join([
        "data: " + json.dumps({"type": "response.created", "response": {"id": "r1"}}),
        "data: " + json.dumps({"type": "response.output_text.delta", "delta": "Hi"}),
        "data: " + json.dumps({"type": "response.completed"}),
        "data: [DONE]",
        "",
    ])
    respx.post("https://api.test/v1/responses").mock(return_value=httpx.Response(200, text=body, headers={"content-type": "text/event-stream"}))
    provider = OpenAIProvider("secret", "https://api.test/v1")
    events = [event async for event in provider.stream(GenerationRequest("future-model", (), ({"type": "message", "role": "user", "content": "Hi"},)))]
    assert [event.event for event in events] == ["response.started", "content.delta", "response.completed"]
