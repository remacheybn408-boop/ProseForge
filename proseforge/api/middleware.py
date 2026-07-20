from __future__ import annotations

import time
from collections import deque
from uuid import uuid4

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        supplied = request.headers.get("x-correlation-id", "")
        correlation_id = supplied[:128] if supplied and supplied.replace("-", "").isalnum() else uuid4().hex
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response


class AgentRateLimitMiddleware(BaseHTTPMiddleware):
    """仅作用于 /api/v3/ 的内存滑动窗口限流。

    按用户（会话 token 解出的 user_id，否则来源 IP）分桶，读写分别计数；
    v1/v2 路由完全不受影响。内存实现随进程生命周期，多副本部署需换共享存储。
    """

    def __init__(self, app, read_per_minute: int = 60, write_per_minute: int = 20):
        super().__init__(app)
        self.read_limit = max(1, read_per_minute)
        self.write_limit = max(1, write_per_minute)
        self._hits: dict[tuple[str, str], deque[float]] = {}

    def _identity(self, request) -> str:
        token = ""
        authorization = request.headers.get("authorization", "")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        if not token:
            token = request.cookies.get("proseforge_session", "")
        if token:
            try:
                return f"user:{request.app.state.auth.decode_token(token).id}"
            except Exception:
                pass
        return f"ip:{request.client.host if request.client else 'unknown'}"

    async def dispatch(self, request, call_next):
        if not request.url.path.startswith("/api/v3/"):
            return await call_next(request)
        kind = "write" if request.method in _WRITE_METHODS else "read"
        limit = self.write_limit if kind == "write" else self.read_limit
        key = (self._identity(request), kind)
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        while hits and now - hits[0] >= 60.0:
            hits.popleft()
        if not hits:
            self._hits.pop(key, None)
            hits = self._hits.setdefault(key, deque())
        if len(hits) >= limit:
            retry_after = max(1, int(60.0 - (now - hits[0])) + 1)
            return JSONResponse(
                status_code=429,
                content={"error": {"code": "RATE_LIMITED", "message": "agent request rate limit exceeded", "retryable": True, "request_id": getattr(request.state, "correlation_id", ""), "details": {}}},
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
        return await call_next(request)
