from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/v1/models":
            self._json({"data": [{"id": "gpt-4.1-mini"}]})
            return
        self.send_error(404)

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/responses":
            self.send_error(404)
            return
        length = int(self.headers.get("content-length", "0"))
        request = json.loads(self.rfile.read(length) or b"{}")
        is_review = isinstance(request.get("text"), dict)
        request_text = json.dumps(request.get("input", {}), ensure_ascii=False)
        response_text = '{"status":"PASS","summary":"mock review","issues":[],"preserve":[],"rewrite_scope":[]}' if is_review else ("Context received: Mira fears deep water." if "Mira fears deep water." in request_text else ("Context received: A first draft written through the browser." if "A first draft written through the browser." in request_text else "Mock provider response"))
        events = [
            {"type": "response.created", "id": "mock-response"},
            {"type": "response.output_text.delta", "delta": response_text},
            {"type": "response.completed"},
        ]
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        encoded = body.encode()
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("content-length", str(len(encoded)))
        self.send_header("connection", "close")
        self.end_headers()
        self.wfile.write(encoded)

    def _json(self, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args: object) -> None:
        return


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
