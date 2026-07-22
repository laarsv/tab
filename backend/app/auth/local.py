"""Anmeldung ohne Google: E-Mail + Passwort.

- Passwörter: scrypt (stdlib hashlib, kein Zusatz-Paket), Format "scrypt$salt$hash".
- Verifizierung/Reset: 6-stellige Codes per System-Mail (SYSTEM_SMTP_*), 30 min gültig.
- Brute-Force-Bremse: In-Memory-Zähler je E-Mail (5 Fehlversuche → 15 min Sperre;
  ein Uvicorn-Prozess, daher ausreichend).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import secrets
import smtplib
import time
from email.message import EmailMessage

from ..config import settings

CODE_GUELTIG_MINUTEN = 30
MAX_FEHLVERSUCHE = 5
SPERRE_SEKUNDEN = 15 * 60

_versuche: dict[str, list] = {}  # email -> [fails, locked_until_ts]


def hash_passwort(passwort: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.scrypt(passwort.encode(), salt=salt.encode(), n=2**14, r=8, p=1)
    return f"scrypt${salt}${h.hex()}"


def verify_passwort(passwort: str, gespeichert: str) -> bool:
    try:
        _, salt, soll = gespeichert.split("$")
        ist = hashlib.scrypt(passwort.encode(), salt=salt.encode(), n=2**14, r=8, p=1)
        return hmac.compare_digest(ist.hex(), soll)
    except Exception:
        return False


def neuer_code() -> tuple[str, str]:
    """(code, gültig_bis_iso)"""
    code = f"{secrets.randbelow(1_000_000):06d}"
    bis = (dt.datetime.utcnow() + dt.timedelta(minutes=CODE_GUELTIG_MINUTEN)).isoformat()
    return code, bis


def code_gueltig(code: str | None, soll: str | None, gueltig_bis: str | None) -> bool:
    if not code or not soll or not gueltig_bis:
        return False
    if dt.datetime.utcnow().isoformat() > gueltig_bis:
        return False
    return hmac.compare_digest(code.strip(), soll)


def gesperrt(email: str) -> bool:
    eintrag = _versuche.get(email.lower())
    return bool(eintrag and eintrag[1] > time.time())


def fehlversuch(email: str) -> None:
    e = _versuche.setdefault(email.lower(), [0, 0.0])
    e[0] += 1
    if e[0] >= MAX_FEHLVERSUCHE:
        e[0] = 0
        e[1] = time.time() + SPERRE_SEKUNDEN


def erfolg(email: str) -> None:
    _versuche.pop(email.lower(), None)


def sende_system_mail(an: str, betreff: str, text: str) -> None:
    """Code-Mails über den System-Absender (SYSTEM_SMTP_*)."""
    msg = EmailMessage()
    msg["From"] = settings.SYSTEM_ABSENDER or settings.SYSTEM_SMTP_USER
    msg["To"] = an
    msg["Subject"] = betreff
    msg.set_content(text)
    port = int(settings.SYSTEM_SMTP_PORT)
    if port == 465:
        smtp = smtplib.SMTP_SSL(settings.SYSTEM_SMTP_HOST, port, timeout=30)
    else:
        smtp = smtplib.SMTP(settings.SYSTEM_SMTP_HOST, port, timeout=30)
        smtp.starttls()
    with smtp:
        smtp.login(settings.SYSTEM_SMTP_USER, settings.SYSTEM_SMTP_PASSWORT)
        smtp.send_message(msg)
