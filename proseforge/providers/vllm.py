from .chat_completions import ChatCompletionsProvider


class VLLMProvider(ChatCompletionsProvider):
    provider_id = "vllm"

    def __init__(self, api_key: str = "", base_url: str = "http://vllm:8000", timeout: float = 30.0):
        super().__init__(api_key, f"{base_url.rstrip('/')}/v1", timeout)
