"""Auth-Dependency: Session aus HttpOnly-Cookie, gegen E-Mail-Allowlist geprüft.
Dazu die Mandanten-Guards: check_gewerbe (Besitzer-Check) und ist_admin."""
from __future__ import annotations

import sqlite3

from fastapi import Depends, HTTPException, Request, status

from ..config import settings
from .session import decode_session

ROLLE_BERATER = "steuerberatung"


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

    berater_id = payload.get("berater")
    if berater_id:
        # Steuerberatung: nur mit bestehendem, nicht gesperrtem Zugang für genau diesen Inhaber. Die Prüfung
        # läuft bei jedem Request — Sperren und Entfernen wirken sofort.
        from ..db import _connect  # lokal: vermeidet Importzyklus

        conn = _connect()
        try:
            z = conn.execute(
                "SELECT id, name, bezeichnung, gesperrt, owner_email FROM berater_zugang WHERE id = ?", (berater_id,)
            ).fetchone()
        finally:
            conn.close()
        if z is None or z["gesperrt"] or z["owner_email"].lower() != email:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="zugang_beendet")
        return {
            "email": email,  # die Daten des Inhabers — so greifen alle Mandanten-Guards unverändert
            "name": z["name"],
            "picture": None,
            "rolle": ROLLE_BERATER,
            "berater_id": z["id"],
            "bezeichnung": z["bezeichnung"],
        }

    return {"email": email, "name": payload.get("name"), "picture": payload.get("picture"), "rolle": "inhaber"}


def nur_inhaber(user: dict = Depends(get_current_user)) -> dict:
    """Dependency für alles, was die Steuerberatung nie darf (Zugänge verwalten …)."""
    if user.get("rolle") == ROLLE_BERATER:
        raise HTTPException(status_code=403, detail="Das ist dem Inhaber vorbehalten.")
    return user


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
    if user.get("rolle") == ROLLE_BERATER:
        return False  # die Steuerberatung ist nie Admin, auch wenn die Daten einem Admin gehören
    return user["email"] in settings.allowed_emails_list
