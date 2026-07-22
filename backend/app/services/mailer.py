"""Mail-Konto je Login: Versand (SMTP) + Grundlage für den Beleg-Import (IMAP).

Zwei Provider-Modi (user_mail.provider):
- 'google' (Default): smtp/imap.gmail.com, Login = eigene Adresse + App-Passwort.
- 'custom': beliebiger Anbieter (z. B. All-Inkl) — Host/Port/Benutzer frei,
  Absender-Adresse fürs From:, optional eigene Import-Adresse.

Das Passwort wird Fernet-verschlüsselt gespeichert (Schlüssel aus JWT_SECRET) —
nie im Klartext, nie in der .env. Versand über Port 587 (STARTTLS) oder 465 (SSL).
"""
from __future__ import annotations

import base64
import hashlib
import smtplib
import sqlite3
from email.message import EmailMessage

from cryptography.fernet import Fernet, InvalidToken

from ..config import settings

GOOGLE_SMTP = ("smtp.gmail.com", 587)
GOOGLE_IMAP = ("imap.gmail.com", 993)


class MailNotConfiguredError(Exception):
    """Für diesen Login ist kein Mail-Konto hinterlegt."""


class MailSendError(Exception):
    """SMTP-Login oder Versand fehlgeschlagen (Meldung ist nutzertauglich)."""


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(f"mail:{settings.JWT_SECRET}".encode()).digest())
    return Fernet(key)


def save_konto(
    conn: sqlite3.Connection,
    email: str,
    passwort: str,
    *,
    provider: str = "google",
    smtp_host: str | None = None,
    smtp_port: int | None = None,
    imap_host: str | None = None,
    imap_port: int | None = None,
    mail_benutzer: str | None = None,
    absender_email: str | None = None,
    import_adresse: str | None = None,
) -> None:
    enc = _fernet().encrypt(passwort.encode()).decode()
    conn.execute(
        """
        INSERT INTO user_mail (email, app_passwort_enc, provider, smtp_host, smtp_port,
                               imap_host, imap_port, mail_benutzer, absender_email, import_adresse)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            app_passwort_enc=excluded.app_passwort_enc, provider=excluded.provider,
            smtp_host=excluded.smtp_host, smtp_port=excluded.smtp_port,
            imap_host=excluded.imap_host, imap_port=excluded.imap_port,
            mail_benutzer=excluded.mail_benutzer, absender_email=excluded.absender_email,
            import_adresse=excluded.import_adresse, updated_at=datetime('now')
        """,
        (email.lower(), enc, provider, smtp_host, smtp_port, imap_host, imap_port,
         mail_benutzer, absender_email, import_adresse),
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


def lade_konto(conn: sqlite3.Connection, user_email: str) -> dict:
    """Aufgelöstes Mail-Konto inkl. entschlüsseltem Passwort und Defaults."""
    row = conn.execute(
        "SELECT * FROM user_mail WHERE email = ?", (user_email.lower(),)
    ).fetchone()
    if row is None:
        raise MailNotConfiguredError(
            "Kein Mail-Konto hinterlegt. Im Profil-Menü unter E-Mail-Versand einrichten."
        )
    try:
        passwort = _fernet().decrypt(row["app_passwort_enc"].encode()).decode()
    except InvalidToken:
        raise MailNotConfiguredError(
            "Gespeichertes Passwort ist nicht mehr lesbar (Secret geändert?) — bitte neu hinterlegen."
        )
    custom = row["provider"] == "custom"
    return {
        "provider": row["provider"],
        "smtp_host": (row["smtp_host"] if custom else None) or GOOGLE_SMTP[0],
        "smtp_port": (row["smtp_port"] if custom else None) or GOOGLE_SMTP[1],
        "imap_host": (row["imap_host"] if custom else None) or GOOGLE_IMAP[0],
        "imap_port": (row["imap_port"] if custom else None) or GOOGLE_IMAP[1],
        "benutzer": (row["mail_benutzer"] if custom else None) or row["email"],
        "absender": (row["absender_email"] if custom else None) or row["email"],
        "import_adresse": row["import_adresse"],
        "passwort": passwort,
        "import_aktiv": bool(row["import_aktiv"]),
        "import_gewerbe_id": row["import_gewerbe_id"],
        "email": row["email"],
    }


def _smtp_verbindung(host: str, port: int) -> smtplib.SMTP:
    if int(port) == 465:
        return smtplib.SMTP_SSL(host, port, timeout=30)
    smtp = smtplib.SMTP(host, port, timeout=30)
    smtp.starttls()
    return smtp


def verify_konto(
    *, smtp_host: str, smtp_port: int, benutzer: str, passwort: str
) -> None:
    """SMTP-Login testen (wirft MailSendError mit klarer Meldung)."""
    try:
        with _smtp_verbindung(smtp_host, smtp_port) as smtp:
            smtp.login(benutzer, passwort)
    except smtplib.SMTPAuthenticationError:
        raise MailSendError(
            "Der Mail-Server hat den Login abgelehnt — Benutzername/Passwort prüfen. "
            "Bei Google muss es ein App-Passwort sein (2-Faktor-Authentifizierung nötig)."
        )
    except OSError as e:
        raise MailSendError(f"Verbindung zu {smtp_host}:{smtp_port} fehlgeschlagen: {e}")


def send_mail(
    conn: sqlite3.Connection,
    absender_email: str,  # = Login-E-Mail (Schlüssel für das Mail-Konto)
    absender_name: str | None,
    an: str,
    betreff: str,
    text: str,
    anhang: tuple[str, bytes] | None = None,  # (dateiname, pdf-bytes)
) -> None:
    konto = lade_konto(conn, absender_email)

    msg = EmailMessage()
    msg["From"] = f"{absender_name} <{konto['absender']}>" if absender_name else konto["absender"]
    msg["To"] = an
    msg["Subject"] = betreff
    msg.set_content(text)
    if anhang:
        name, data = anhang
        msg.add_attachment(data, maintype="application", subtype="pdf", filename=name)

    try:
        with _smtp_verbindung(konto["smtp_host"], konto["smtp_port"]) as smtp:
            smtp.login(konto["benutzer"], konto["passwort"])
            smtp.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        raise MailSendError(
            "Der Mail-Server hat den Login abgelehnt — Zugangsdaten im Profil-Menü neu hinterlegen."
        )
    except (smtplib.SMTPException, OSError) as e:
        raise MailSendError(f"Versand fehlgeschlagen: {e}")
