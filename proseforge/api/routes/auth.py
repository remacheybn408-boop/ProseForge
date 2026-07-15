from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    user_id: str = Field(min_length=1)
    email: str
    password: str = Field(min_length=12)
    password_hash: str


@router.post("/login")
async def login(request: LoginRequest, http_request: Request) -> dict[str, str]:
    service = http_request.app.state.auth
    if not service.verify_password(request.password, request.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")
    from proseforge.application.auth.service import AuthUser
    return {"access_token": service.issue_token(AuthUser(request.user_id, request.email)), "token_type": "bearer"}
