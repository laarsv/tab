"""Login-Endpunkte: POST /api/auth/login, GET /api/auth/me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..config import settings
from .deps import get_current_user
from .security import create_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class MeOut(BaseModel):
    username: str


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn) -> TokenOut:
    ok = body.username == settings.ADMIN_USERNAME and verify_password(
        body.password, settings.ADMIN_PASSWORD_HASH
    )
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Benutzername oder Passwort falsch."
        )
    return TokenOut(access_token=create_token(settings.ADMIN_USERNAME))


@router.get("/me", response_model=MeOut)
def me(user: str = Depends(get_current_user)) -> MeOut:
    return MeOut(username=user)
