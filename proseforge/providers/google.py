from .http_base import HttpJsonProvider


class GoogleProvider(HttpJsonProvider):
    provider_id = "google"
    models_path = "/models"
    generation_path = "/generateContent"
