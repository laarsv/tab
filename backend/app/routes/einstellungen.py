"""Persönliche Einstellungen des eingeloggten Nutzers: Gmail-App-Passwort für den
Rechnungsversand. Wird beim Speichern per SMTP-Login verifiziert und Fernet-
verschlüsselt in `user_mail` abgelegt — individuell je Login, nicht in der .env."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services.mail_import import plus_adresse
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
    row = db.execute(
        "SELECT import_aktiv, import_gewerbe_id FROM user_mail WHERE email = ?",
        (user["email"],),
    ).fetchone()
    return {
        "email": user["email"],
        "konfiguriert": is_configured(db, user["email"]),
        "plus_adresse": plus_adresse(user["email"]),
        "import_aktiv": bool(row["import_aktiv"]) if row else False,
        "import_gewerbe_id": row["import_gewerbe_id"] if row else None,
    }


class MailImportIn(BaseModel):
    aktiv: bool
    gewerbe_id: int | None = None


@router.put("/mail/import")
def mail_import_speichern(
    body: MailImportIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    if not is_configured(db, user["email"]):
        raise HTTPException(400, "Zuerst das App-Passwort hinterlegen — der Abruf läuft über IMAP.")
    if body.gewerbe_id is not None:
        check_gewerbe(db, user, body.gewerbe_id)
    db.execute(
        "UPDATE user_mail SET import_aktiv = ?, import_gewerbe_id = ?, "
        "updated_at = datetime('now') WHERE email = ?",
        (1 if body.aktiv else 0, body.gewerbe_id, user["email"]),
    )
    db.commit()
    return mail_status(user, db)


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
