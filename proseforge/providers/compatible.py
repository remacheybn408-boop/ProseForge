from .http_base import HttpJsonProvider


class OpenAICompatibleProvider(HttpJsonProvider):
    provider_id = "custom"


class AnthropicCompatibleProvider(HttpJsonProvider):
    provider_id = "custom-anthropic"
