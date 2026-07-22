"""Beleg-Eingang per E-Mail: „Schick den Beleg an deine-adresse+tab@…".

Für jeden Login mit aktiviertem Import holt der Scheduler per IMAP
(imap.gmail.com, gleiches App-Passwort wie der Versand) Mails der letzten
14 Tage ab, die an die eigene +tab-Adresse gingen, und legt PDF/JPG/PNG/XML-
Anhänge in den Beleg-Eingang. Sicherungen:
- Nur Absender, die in Tab freigeschaltet sind (Allowlist) — Fremde können
  nichts in den Eingang schieben.
- Dedup über Message-ID (Tabelle mail_import) — gelesen/ungelesen ist egal,
  nichts wird doppelt importiert, keine Mail wird verändert oder gelöscht.
"""
from __future__ import annotations

import datetime as dt
import email
import email.utils
import imaplib
import json
import logging
import sqlite3

from ..config import settings
from .beleg_store import BelegAbgelehnt, speichere_beleg

log = logging.getLogger("tab.mail_import")

IMAP_HOST = "smtp.gmail.com".replace("smtp", "imap")  # imap.gmail.com
SUCHFENSTER_TAGE = 14


def plus_adresse(email_addr: str) -> str:
    local, dom = email_addr.split("@", 1)
    return f"{local}+tab@{dom}"


def importiere_nachricht(
    conn: sqlite3.Connection, user_email: str, gewerbe_id: int, msg_bytes: bytes
) -> list[int] | None:
    """Verarbeitet eine Mail: Absender-Check, Dedup, Anhänge speichern.
    Gibt Beleg-IDs zurück (leer = keine passenden Anhänge), None = übersprungen."""
    msg = email.message_from_bytes(msg_bytes)
    message_id = (msg.get("Message-ID") or "").strip()
    if not message_id:
        return None
    if conn.execute(
        "SELECT 1 FROM mail_import WHERE email = ? AND message_id = ?",
        (user_email, message_id),
    ).fetchone():
        return None

    absender = (email.utils.parseaddr(msg.get("From") or "")[1] or "").lower()
    if not settings.is_email_allowed(absender):
        log.info("Mail-Import %s: Absender %s nicht freigeschaltet — übersprungen",
                 user_email, absender)
        conn.execute(  # trotzdem als verarbeitet merken, sonst prüfen wir sie ewig
            "INSERT OR IGNORE INTO mail_import (email, message_id, beleg_ids) VALUES (?, ?, ?)",
            (user_email, message_id, None),
        )
        conn.commit()
        return None

    beleg_ids: list[int] = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        dateiname = part.get_filename()
        if not dateiname and part.get_content_disposition() != "attachment":
            continue
        daten = part.get_payload(decode=True)
        if not daten:
            continue
        try:
            beleg_ids.append(
                speichere_beleg(
                    conn,
                    gewerbe_id=gewerbe_id,
                    original_name=dateiname or "beleg",
                    data=daten,
                    content_type=part.get_content_type(),
                )
            )
        except BelegAbgelehnt:
            continue  # z. B. Mail-Signatur-Bilder, zu große Dateien

    conn.execute(
        "INSERT OR IGNORE INTO mail_import (email, message_id, beleg_ids) VALUES (?, ?, ?)",
        (user_email, message_id, json.dumps(beleg_ids) if beleg_ids else None),
    )
    conn.commit()
    return beleg_ids


def _hole_fuer_nutzer(conn: sqlite3.Connection, user_email: str, app_passwort: str,
                      gewerbe_id: int) -> int:
    seit = (dt.date.today() - dt.timedelta(days=SUCHFENSTER_TAGE)).strftime("%d-%b-%Y")
    ziel = plus_adresse(user_email)
    importiert = 0
    M = imaplib.IMAP4_SSL(IMAP_HOST, 993, timeout=30)
    try:
        M.login(user_email, app_passwort)
        M.select("INBOX", readonly=True)  # readonly: wir verändern nichts am Postfach
        typ, daten = M.search(None, f'(SINCE {seit} TO "{ziel}")')
        if typ != "OK":
            return 0
        for num in daten[0].split():
            typ, teile = M.fetch(num, "(RFC822)")
            if typ != "OK" or not teile or teile[0] is None:
                continue
            ids = importiere_nachricht(conn, user_email, gewerbe_id, teile[0][1])
            if ids:
                importiert += len(ids)
    finally:
        try:
            M.logout()
        except Exception:
            pass
    return importiert


def run_mail_import(conn: sqlite3.Connection) -> int:
    """Alle Nutzer mit aktivem Import abarbeiten. Gibt Anzahl neuer Belege zurück."""
    from .mailer import _fernet  # lazy: Fernet-Key aus JWT_SECRET

    gesamt = 0
    nutzer = conn.execute(
        "SELECT * FROM user_mail WHERE import_aktiv = 1"
    ).fetchall()
    for u in nutzer:
        gid = u["import_gewerbe_id"]
        if gid is None or not conn.execute(
            "SELECT 1 FROM gewerbe WHERE id = ? AND aktiv = 1", (gid,)
        ).fetchone():
            row = conn.execute(
                "SELECT id FROM gewerbe WHERE aktiv = 1 ORDER BY id LIMIT 1"
            ).fetchone()
            gid = row["id"] if row else None
        if gid is None:
            continue
        try:
            passwort = _fernet().decrypt(u["app_passwort_enc"].encode()).decode()
            gesamt += _hole_fuer_nutzer(conn, u["email"], passwort, gid)
        except Exception:
            log.exception("Mail-Import für %s fehlgeschlagen", u["email"])
    return gesamt
