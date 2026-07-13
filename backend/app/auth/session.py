"""Session-JWT (im HttpOnly-Cookie). Trägt E-Mail + Anzeigename/Bild."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from ..config import settings

ALGORITHM = "HS256"


def encode_session(email: str, name: str | None = None, picture: str | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "email": email,
        "name": name,
        "picture": picture,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.JWT_TTL_DAYS)).timestamp()),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_session(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
