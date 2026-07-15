from .http_base import HttpJsonProvider


class VLLMProvider(HttpJsonProvider):
    provider_id = "vllm"

    def __init__(self, api_key: str = "", base_url: str = "http://vllm:8000", timeout: float = 30.0):
        super().__init__(api_key, base_url, timeout)
