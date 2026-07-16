from __future__ import annotations

from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        supplied = request.headers.get("x-correlation-id", "")
        correlation_id = supplied[:128] if supplied and supplied.replace("-", "").isalnum() else uuid4().hex
        request.state.correlation_id = correlation_id
        response = await call_next(request)
        response.headers["x-correlation-id"] = correlation_id
        return response
