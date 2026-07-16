from proseforge.api.routes.providers import CustomModelRequest


def test_custom_model_request_accepts_future_model_id():
    request = CustomModelRequest(provider="custom", model_id="future-model-2027")

    assert request.model_id == "future-model-2027"
