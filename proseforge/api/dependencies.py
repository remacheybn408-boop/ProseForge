from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

_bearer = HTTPBearer(auto_error=False)


async def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthUser:
    token = credentials.credentials if credentials else request.cookies.get("proseforge_session")
    if not token:
        raise HTTPException(status_code=401, detail="authentication required")
    try:
        return request.app.state.auth.decode_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="invalid session token") from exc


def unit_of_work(request: Request) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(request.app.state.session_factory)
