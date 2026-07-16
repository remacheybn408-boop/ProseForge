from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from urllib.parse import urlsplit

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


def require_admin(user: AuthUser) -> AuthUser:
    if user.role != "ADMIN":
        raise HTTPException(status_code=403, detail="administrator access required")
    return user


async def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    expected = urlsplit(request.app.state.settings.public_url)
    actual = urlsplit(origin)
    if (actual.scheme, actual.netloc) != (expected.scheme, expected.netloc):
        raise HTTPException(status_code=403, detail="origin is not allowed")


def unit_of_work(request: Request) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(request.app.state.session_factory)
