from __future__ import annotations

import json
import time
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
        # e2e professional-flow step 9 以 model="mock-slow" 请求拖慢生成：
        # 章节生成太快会让 pause/resume/retry/cancel 的持久状态迁移错过轮询窗口。
        if request.get("model") == "mock-slow":
            time.sleep(2)
        is_review = isinstance(request.get("text"), dict)
        response_text = '{"status":"PASS","summary":"mock review","issues":[],"preserve":[],"rewrite_scope":[]}' if is_review else "Mock provider response"
        events = [
            {"type": "response.created", "id": "mock-response"},
            {"type": "response.output_text.delta", "delta": response_text},
            {"type": "response.completed", "usage": {"input_tokens": 24, "output_tokens": 12, "total_tokens": 36}},
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
