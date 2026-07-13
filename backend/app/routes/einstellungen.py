"""Persönliche Einstellungen des eingeloggten Nutzers: Gmail-App-Passwort für den
Rechnungsversand. Wird beim Speichern per SMTP-Login verifiziert und Fernet-
verschlüsselt in `user_mail` abgelegt — individuell je Login, nicht in der .env."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import get_current_user
from ..db import get_db
from ..services.mailer import (
    MailNotConfiguredError,
    MailSendError,
    delete_app_passwort,
    is_configured,
    save_app_passwort,
    send_mail,
    verify_login,
)

router = APIRouter(prefix="/api/einstellungen", tags=["einstellungen"])


@router.get("/mail")
def mail_status(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    return {"email": user["email"], "konfiguriert": is_configured(db, user["email"])}


class MailIn(BaseModel):
    app_passwort: str = Field(min_length=8, max_length=100)


@router.put("/mail")
def mail_speichern(
    body: MailIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    passwort = body.app_passwort.replace(" ", "")  # Google zeigt es mit Leerzeichen an
    try:
        verify_login(user["email"], passwort)
    except MailSendError as e:
        raise HTTPException(400, str(e))
    save_app_passwort(db, user["email"], passwort)
    return {"email": user["email"], "konfiguriert": True}


@router.delete("/mail", status_code=204)
def mail_entfernen(
    user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    delete_app_passwort(db, user["email"])


@router.post("/mail/test")
def mail_test(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    try:
        send_mail(
            db,
            absender_email=user["email"],
            absender_name=user.get("name"),
            an=user["email"],
            betreff="Tab: Test-Mail",
            text="Der Rechnungsversand aus Tab funktioniert. Diese Mail ging an dich selbst.",
        )
    except (MailNotConfiguredError, MailSendError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True}
