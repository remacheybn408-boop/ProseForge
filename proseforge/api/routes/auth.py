from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from proseforge.api.dependencies import unit_of_work
from proseforge.infrastructure.database.uow import SqlAlchemyUnitOfWork

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12)


class SetupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12)


@router.post("/setup", status_code=status.HTTP_201_CREATED)
async def setup_admin(
    payload: SetupRequest,
    http_request: Request,
    uow: Annotated[SqlAlchemyUnitOfWork, Depends(unit_of_work)],
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
) -> dict[str, str]:
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
    if password_hash is None or not http_request.app.state.auth.verify_password(payload.password, password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    from proseforge.application.auth.service import AuthUser
    token = http_request.app.state.auth.issue_token(AuthUser(user_id, email))
    response.set_cookie("proseforge_session", token, httponly=True, secure=False, samesite="lax", max_age=3600, path="/")
    return {"access_token": token, "token_type": "bearer"}
