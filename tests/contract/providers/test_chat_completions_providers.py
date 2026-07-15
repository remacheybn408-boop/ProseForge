import json

import httpx
import pytest
import respx

from proseforge.domain.ports.model_provider import GenerationRequest
from proseforge.providers.baidu import BaiduProvider
from proseforge.providers.cohere import CohereProvider
from proseforge.providers.dashscope import DashScopeProvider
from proseforge.providers.deepseek import DeepSeekProvider
from proseforge.providers.kimi import KimiProvider
from proseforge.providers.minimax import MiniMaxProvider
from proseforge.providers.mistral import MistralProvider
from proseforge.providers.tencent import TencentProvider
from proseforge.providers.volcengine import VolcEngineProvider
from proseforge.providers.xai import XAIProvider
from proseforge.providers.zhipu import ZhipuProvider


@pytest.mark.parametrize(
    "factory",
    [
        BaiduProvider,
        CohereProvider,
        DashScopeProvider,
        DeepSeekProvider,
        KimiProvider,
        MiniMaxProvider,
        MistralProvider,
        TencentProvider,
        VolcEngineProvider,
        XAIProvider,
        ZhipuProvider,
    ],
)
@pytest.mark.asyncio
@respx.mock
async def test_chat_provider_contract_preserves_unknown_models_and_streams(factory) -> None:
    base_url = "https://vendor.test/v1"
    models = respx.get(f"{base_url}/models").mock(return_value=httpx.Response(200, json={"data": [{"id": "future-model"}]}))
    completion = respx.post(f"{base_url}/chat/completions").mock(
        return_value=httpx.Response(
            200,
            content=(
                'data: {"id":"resp-1","choices":[{"delta":{"content":"Hello"}}]}\n\n'
                'data: {"id":"resp-1","usage":{"prompt_tokens":2,"completion_tokens":1}}\n\n'
                "data: [DONE]\n\n"
            ),
            headers={"content-type": "text/event-stream"},
        )
    )
    provider = factory("secret", base_url=base_url)
    listed = await provider.list_models()
    events = [
        event
        async for event in provider.stream(
            GenerationRequest("future-model", ({"text": "system"},), ({"role": "user", "text": "Hi"},))
        )
    ]
    assert models.called
    assert listed[0].model_id == "future-model"
    assert completion.called
    assert completion.calls[0].request.headers["authorization"] == "Bearer secret"
    body = json.loads(completion.calls[0].request.content)
    assert body["model"] == "future-model"
    assert body["messages"][-1] == {"role": "user", "content": "Hi"}
    assert [event.event for event in events] == ["response.started", "content.delta", "usage.updated", "response.completed"]
    assert events[1].text == "Hello"
