"""Session-JWT (im HttpOnly-Cookie). Trägt E-Mail + Anzeigename/Bild."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from ..config import settings

ALGORITHM = "HS256"
BERATER_TTL_TAGE = 7


def encode_session(email: str, name: str | None = None, picture: str | None = None, berater: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    # Steuerberatung: eigene Sitzung (kürzer), „email“ ist die des Inhabers, „berater“ die Zugangs-ID.
    tage = min(settings.JWT_TTL_DAYS, BERATER_TTL_TAGE) if berater else settings.JWT_TTL_DAYS
    payload = {
        "email": email,
        "name": name,
        "picture": picture,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=tage)).timestamp()),
    }
    if berater:
        payload["berater"] = int(berater)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_session(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        return None
