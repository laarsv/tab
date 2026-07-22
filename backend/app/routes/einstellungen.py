"""Persönliche Einstellungen des eingeloggten Nutzers: Mail-Konto für Versand +
Beleg-Import. Provider 'google' (App-Passwort) oder 'custom' (eigener Mail-Server,
z. B. All-Inkl). Wird beim Speichern per SMTP-Login verifiziert und verschlüsselt
abgelegt — individuell je Login, nicht in der .env."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services.mail_import import import_ziel, plus_adresse
from ..services.mailer import (
    MailNotConfiguredError,
    MailSendError,
    delete_app_passwort,
    is_configured,
    lade_konto,
    save_konto,
    send_mail,
    verify_konto,
)

router = APIRouter(prefix="/api/einstellungen", tags=["einstellungen"])


@router.get("/mail")
def mail_status(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        "SELECT * FROM user_mail WHERE email = ?", (user["email"],)
    ).fetchone()
    if row is None:
        return {
            "email": user["email"],
            "konfiguriert": False,
            "provider": "google",
            "absender": user["email"],
            "import_ziel": plus_adresse(user["email"]),
            "import_aktiv": False,
            "import_gewerbe_id": None,
            "smtp_host": None, "smtp_port": None, "imap_host": None, "imap_port": None,
            "mail_benutzer": None, "absender_email": None, "import_adresse": None,
        }
    konto = lade_konto(db, user["email"])
    return {
        "email": user["email"],
        "konfiguriert": True,
        "provider": row["provider"],
        "absender": konto["absender"],
        "import_ziel": import_ziel(konto),
        "import_aktiv": bool(row["import_aktiv"]),
        "import_gewerbe_id": row["import_gewerbe_id"],
        "smtp_host": row["smtp_host"], "smtp_port": row["smtp_port"],
        "imap_host": row["imap_host"], "imap_port": row["imap_port"],
        "mail_benutzer": row["mail_benutzer"], "absender_email": row["absender_email"],
        "import_adresse": row["import_adresse"],
    }


class MailIn(BaseModel):
    provider: str = "google"  # google | custom
    app_passwort: str = Field(min_length=4, max_length=200)
    smtp_host: str | None = None
    smtp_port: int | None = Field(default=None, ge=1, le=65535)
    imap_host: str | None = None
    imap_port: int | None = Field(default=None, ge=1, le=65535)
    mail_benutzer: str | None = None
    absender_email: str | None = None
    import_adresse: str | None = None

    @field_validator("provider")
    @classmethod
    def _v_provider(cls, v: str) -> str:
        if v not in ("google", "custom"):
            raise ValueError("provider muss 'google' oder 'custom' sein.")
        return v


@router.put("/mail")
def mail_speichern(
    body: MailIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    passwort = body.app_passwort.strip()
    if body.provider == "google":
        passwort = passwort.replace(" ", "")  # Google zeigt App-Passwörter mit Leerzeichen
        smtp_host, smtp_port = "smtp.gmail.com", 587
        benutzer = user["email"]
        felder = {}
    else:
        if not (body.smtp_host or "").strip():
            raise HTTPException(400, "SMTP-Host fehlt (z. B. w0123456.kasserver.com).")
        if not (body.mail_benutzer or "").strip():
            raise HTTPException(400, "Benutzername fehlt (meist die Mail-Adresse).")
        if "@" not in (body.absender_email or ""):
            raise HTTPException(400, "Absender-Adresse fehlt (steht auf den Rechnungen).")
        smtp_host = body.smtp_host.strip()
        smtp_port = body.smtp_port or 587
        benutzer = body.mail_benutzer.strip()
        felder = {
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "imap_host": (body.imap_host or "").strip() or smtp_host,
            "imap_port": body.imap_port or 993,
            "mail_benutzer": benutzer,
            "absender_email": body.absender_email.strip(),
            "import_adresse": (body.import_adresse or "").strip() or None,
        }
    try:
        verify_konto(smtp_host=smtp_host, smtp_port=smtp_port, benutzer=benutzer, passwort=passwort)
    except MailSendError as e:
        raise HTTPException(400, str(e))
    save_konto(db, user["email"], passwort, provider=body.provider, **felder)
    return mail_status(user, db)


@router.delete("/mail", status_code=204)
def mail_entfernen(
    user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    delete_app_passwort(db, user["email"])


@router.post("/mail/test")
def mail_test(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    try:
        konto = lade_konto(db, user["email"])
        send_mail(
            db,
            absender_email=user["email"],
            absender_name=user.get("name"),
            an=konto["absender"],
            betreff="Tab: Test-Mail",
            text="Der Rechnungsversand aus Tab funktioniert. Diese Mail ging an dein Absender-Postfach.",
        )
    except (MailNotConfiguredError, MailSendError) as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


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
        raise HTTPException(400, "Zuerst das Mail-Konto hinterlegen — der Abruf läuft über IMAP.")
    if body.gewerbe_id is not None:
        check_gewerbe(db, user, body.gewerbe_id)
    db.execute(
        "UPDATE user_mail SET import_aktiv = ?, import_gewerbe_id = ?, "
        "updated_at = datetime('now') WHERE email = ?",
        (1 if body.aktiv else 0, body.gewerbe_id, user["email"]),
    )
    db.commit()
    return mail_status(user, db)
