from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from proseforge.domain.common.errors import DomainError


async def domain_error_handler(request: Request, error: DomainError) -> JSONResponse:
    return JSONResponse(status_code=409 if error.code == "CONFLICT" else 400, content={"error": {"code": error.code, "message": str(error), "retryable": error.retryable, "request_id": request.headers.get("x-request-id", "") , "details": {}}})
