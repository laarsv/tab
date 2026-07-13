"""Rechnungsversand über das Google-Konto des eingeloggten Nutzers.

Jeder Nutzer hinterlegt sein eigenes Gmail-App-Passwort (Google-Konto → Sicherheit →
App-Passwörter, 2FA nötig). Gespeichert wird es Fernet-verschlüsselt in `user_mail`
(Schlüssel aus JWT_SECRET abgeleitet) — nie im Klartext, nie in der .env.
Versand via smtp.gmail.com (funktioniert für gmail.com UND Google-Workspace-Adressen);
die Mail liegt danach im „Gesendet"-Ordner des Nutzers.
"""
from __future__ import annotations

import base64
import hashlib
import smtplib
import sqlite3
from email.message import EmailMessage

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587


class MailNotConfiguredError(Exception):
    """Für diesen Login ist kein App-Passwort hinterlegt."""


class MailSendError(Exception):
    """SMTP-Login oder Versand fehlgeschlagen (Meldung ist nutzertauglich)."""


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(f"mail:{settings.JWT_SECRET}".encode()).digest())
    return Fernet(key)


def save_app_passwort(conn: sqlite3.Connection, email: str, app_passwort: str) -> None:
    enc = _fernet().encrypt(app_passwort.encode()).decode()
    conn.execute(
        "INSERT INTO user_mail (email, app_passwort_enc) VALUES (?, ?) "
        "ON CONFLICT(email) DO UPDATE SET app_passwort_enc=excluded.app_passwort_enc, "
        "updated_at=datetime('now')",
        (email.lower(), enc),
    )
    conn.commit()


def delete_app_passwort(conn: sqlite3.Connection, email: str) -> None:
    conn.execute("DELETE FROM user_mail WHERE email = ?", (email.lower(),))
    conn.commit()


def is_configured(conn: sqlite3.Connection, email: str) -> bool:
    return (
        conn.execute("SELECT 1 FROM user_mail WHERE email = ?", (email.lower(),)).fetchone()
        is not None
    )


def _load_app_passwort(conn: sqlite3.Connection, email: str) -> str:
    row = conn.execute(
        "SELECT app_passwort_enc FROM user_mail WHERE email = ?", (email.lower(),)
    ).fetchone()
    if row is None:
        raise MailNotConfiguredError(
            "Kein App-Passwort hinterlegt. Im Profil-Menü unter E-Mail-Versand einrichten."
        )
    try:
        return _fernet().decrypt(row["app_passwort_enc"].encode()).decode()
    except InvalidToken:
        raise MailNotConfiguredError(
            "Gespeichertes App-Passwort ist nicht mehr lesbar (Secret geändert?) — bitte neu hinterlegen."
        )


def verify_login(email: str, app_passwort: str) -> None:
    """SMTP-Login testen (wirft MailSendError mit klarer Meldung)."""
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            smtp.starttls()
            smtp.login(email, app_passwort)
    except smtplib.SMTPAuthenticationError:
        raise MailSendError(
            "Google hat den Login abgelehnt. Ist es ein App-Passwort (nicht das normale Passwort)? "
            "App-Passwörter brauchen aktivierte 2-Faktor-Authentifizierung."
        )
    except OSError as e:
        raise MailSendError(f"SMTP-Verbindung fehlgeschlagen: {e}")


def send_mail(
    conn: sqlite3.Connection,
    absender_email: str,
    absender_name: str | None,
    an: str,
    betreff: str,
    text: str,
    anhang: tuple[str, bytes] | None = None,  # (dateiname, pdf-bytes)
) -> None:
    app_passwort = _load_app_passwort(conn, absender_email)

    msg = EmailMessage()
    msg["From"] = f"{absender_name} <{absender_email}>" if absender_name else absender_email
    msg["To"] = an
    msg["Subject"] = betreff
    msg.set_content(text)
    if anhang:
        name, data = anhang
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=name)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(absender_email, app_passwort)
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise MailSendError(
            "Google hat den Login abgelehnt — App-Passwort im Profil-Menü neu hinterlegen."
        )
    except (smtplib.SMTPException, OSError) as e:
        raise MailSendError(f"Versand fehlgeschlagen: {e}")
