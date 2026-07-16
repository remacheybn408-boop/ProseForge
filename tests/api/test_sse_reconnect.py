from proseforge.api.sse.encoder import encode_sse


def test_sse_encoder_keeps_event_id():
    assert encode_sse(event_id="42", event="content.delta", data={"text": "hi"}).startswith(b"id: 42\n")
