"""Auth-Dependency: Session aus HttpOnly-Cookie, gegen E-Mail-Allowlist geprüft."""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from ..config import settings
from .session import decode_session


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_authenticated")

    payload = decode_session(token)
    email = (payload or {}).get("email", "").lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_session")

    # Allowlist (E-Mail oder Domain) bei jedem Request prüfen → Entzug wirkt sofort.
    if not settings.is_email_allowed(email):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_allowed")

    return {"email": email, "name": payload.get("name"), "picture": payload.get("picture")}
