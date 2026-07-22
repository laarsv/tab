"""Auth-Dependency: Session aus HttpOnly-Cookie, gegen E-Mail-Allowlist geprüft.
Dazu die Mandanten-Guards: check_gewerbe (Besitzer-Check) und ist_admin."""
from __future__ import annotations

import sqlite3

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

    # Offene Registrierung: jedes Google-Konto darf rein; sonst Allowlist
    # (E-Mail oder Domain) bei jedem Request prüfen → Entzug wirkt sofort.
    if not settings.OPEN_SIGNUP and not settings.is_email_allowed(email):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not_allowed")

    return {"email": email, "name": payload.get("name"), "picture": payload.get("picture")}


def check_gewerbe(db: sqlite3.Connection, user: dict, gewerbe_id: int) -> sqlite3.Row:
    """Mandanten-Guard: Gewerbe muss existieren und dem Nutzer gehören.

    owner_email NULL = herrenloser Alt-Bestand: seit der offenen Registrierung
    nur noch für Admins sichtbar (zum Zuordnen). Fremde Gewerbe antworten mit
    404 (nicht 403 — keine Existenz verraten).
    """
    row = db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    if row["owner_email"] is None:
        if not ist_admin(user):
            raise HTTPException(404, "Gewerbe nicht gefunden.")
    elif row["owner_email"] != user["email"]:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    return row


def ist_admin(user: dict) -> bool:
    """Admins = die explizit in ALLOWED_EMAILS gelisteten Adressen (nicht die
    Domain-Nutzer). Nur Admins dürfen z. B. das Komplett-Backup ziehen."""
    return user["email"] in settings.allowed_emails_list
