from proseforge.providers.usage import normalize_provider_usage


def test_google_usage_metadata_maps_to_common_usage_delta():
    delta = normalize_provider_usage("google", {"usageMetadata": {"promptTokenCount": 4, "candidatesTokenCount": 3, "totalTokenCount": 7}})

    assert delta.input_tokens == 4
    assert delta.output_tokens == 3
    assert delta.total_tokens == 7
    assert delta.source == "provider"


def test_missing_usage_is_explicitly_estimated():
    delta = normalize_provider_usage("ollama", {}, estimated=True)

    assert delta.source == "estimated"
    assert delta.total_tokens == 0
