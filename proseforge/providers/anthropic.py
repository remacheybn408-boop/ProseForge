from .http_base import HttpJsonProvider


class AnthropicProvider(HttpJsonProvider):
    provider_id = "anthropic"
    models_path = "/models"
    generation_path = "/messages"
