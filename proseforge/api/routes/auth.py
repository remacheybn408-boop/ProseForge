from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from proseforge.api.dependencies import current_user, require_same_origin, unit_of_work
from proseforge.application.auth.service import AuthUser
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12)


class SetupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12)


@router.post("/setup", status_code=status.HTTP_201_CREATED)
async def setup_admin(
    payload: SetupRequest,
    http_request: Request,
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
    _csrf: Annotated[None, Depends(require_same_origin)],
) -> dict[str, str]:
    async with uow:
        if await uow.users.count() > 0:
            raise HTTPException(status_code=409, detail="initial setup already completed")
        try:
            user = await uow.users.create(payload.email, http_request.app.state.auth.hash_password(payload.password), "ADMIN")
            await uow.commit()
        except Exception as exc:
            raise HTTPException(status_code=409, detail="email already registered") from exc
        return {"id": user.id, "email": user.email, "role": user.role}


@router.post("/login")
async def login(
    payload: LoginRequest,
    http_request: Request,
    response: Response,
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
    _csrf: Annotated[None, Depends(require_same_origin)],
) -> dict[str, str]:
    client_host = http_request.client.host if http_request.client else "unknown"
    identity = f"{client_host}:{payload.email.strip().casefold()}"
    if not await http_request.app.state.login_rate_limiter.allow(identity):
        raise HTTPException(status_code=429, detail="too many login attempts", headers={"Retry-After": "60"})
    async with uow:
        user = await uow.users.get_by_email(payload.email)
        if user is None:
            password_hash = None
            user_id = ""
            email = payload.email
        else:
            password_hash = user.password_hash
            user_id = user.id
            email = user.email
            role = user.role
    if password_hash is None or not http_request.app.state.auth.verify_password(payload.password, password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    from proseforge.application.auth.service import AuthUser
    token = http_request.app.state.auth.issue_token(AuthUser(user_id, email, role))
    is_public_https = http_request.app.state.settings.public_url.lower().startswith("https://")
    is_production = http_request.app.state.settings.environment.lower() in {"production", "prod"}
    response.set_cookie("proseforge_session", token, httponly=True, secure=is_public_https or is_production, samesite="lax", max_age=3600, path="/")
    return {"access_token": token, "token_type": "bearer"}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, _csrf: Annotated[None, Depends(require_same_origin)]) -> None:
    response.delete_cookie("proseforge_session", path="/")


@router.get("/me")
async def me(user: Annotated[AuthUser, Depends(current_user)]) -> dict[str, str]:
    return {"id": user.id, "email": user.email, "role": user.role}


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChangeRequest,
    user: Annotated[AuthUser, Depends(current_user)],
    http_request: Request,
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
    _csrf: Annotated[None, Depends(require_same_origin)],
) -> None:
    async with uow:
        record = await uow.users.get_by_id(user.id)
        if record is None or not http_request.app.state.auth.verify_password(payload.current_password, record.password_hash):
            raise HTTPException(status_code=401, detail="invalid current password")
        record.password_hash = http_request.app.state.auth.hash_password(payload.new_password)
        await uow.commit()
