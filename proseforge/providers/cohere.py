from .chat_completions import ChatCompletionsProvider


class CohereProvider(ChatCompletionsProvider):
    provider_id = "cohere"
    default_base_url = "https://api.cohere.com/compatibility/v1"
