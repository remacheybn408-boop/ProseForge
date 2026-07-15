from .http_base import HttpJsonProvider


class OllamaProvider(HttpJsonProvider):
    provider_id = "ollama"

    def __init__(self, api_key: str = "", base_url: str = "http://ollama:11434", timeout: float = 30.0):
        super().__init__(api_key, base_url, timeout)
