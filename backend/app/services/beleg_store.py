"""Zentrale Beleg-Ablage — genutzt vom Upload (routes/belege.py), vom
PWA-Share-Target und vom Mail-Import. Validiert Typ/Größe, speichert die Datei
unter UPLOAD_ROOT und legt den beleg-Datensatz an (Eingang, buchung_id NULL).
Bei E-Rechnungs-XML wird die Fälligkeit automatisch übernommen."""
from __future__ import annotations

import os
import sqlite3
import uuid

from ..config import settings
from .beleg_extract import parse_e_rechnung

ALLOWED = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "application/xml": ".xml",
    "text/xml": ".xml",
}


class BelegAbgelehnt(Exception):
    """Datei nicht speicherbar (Typ/Größe) — Meldung ist nutzertauglich."""


def speichere_beleg(
    conn: sqlite3.Connection,
    *,
    gewerbe_id: int,
    original_name: str,
    data: bytes,
    content_type: str | None,
    faellig_am: str | None = None,
    buchung_id: int | None = None,
) -> int:
    """Speichert Datei + beleg-Zeile (ohne Commit) und gibt die Beleg-ID zurück."""
    ext = ALLOWED.get((content_type or "").lower())
    if ext is None and (original_name or "").lower().endswith(".xml"):
        ext = ".xml"  # Browser/Mailclients melden XML teils ohne brauchbaren MIME-Typ
        content_type = "application/xml"
    if ext is None:
        raise BelegAbgelehnt("Nur PDF, JPG, PNG oder XML (E-Rechnung) erlaubt.")
    if len(data) == 0:
        raise BelegAbgelehnt("Datei ist leer.")
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise BelegAbgelehnt(f"Datei zu groß (max. {settings.MAX_UPLOAD_MB} MB).")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(settings.UPLOAD_ROOT, exist_ok=True)
    with open(os.path.join(settings.UPLOAD_ROOT, stored_name), "wb") as fh:
        fh.write(data)

    if ext == ".xml" and not faellig_am:
        parsed = parse_e_rechnung(data)
        if parsed and parsed.get("faellig_am"):
            faellig_am = parsed["faellig_am"]

    original = os.path.basename(original_name or f"beleg{ext}")
    cur = conn.execute(
        """
        INSERT INTO beleg (gewerbe_id, buchung_id, original_name, stored_name, content_type,
                           size_bytes, faellig_am)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (gewerbe_id, buchung_id, original, stored_name, content_type, len(data),
         faellig_am or None),
    )
    return cur.lastrowid


def default_gewerbe_id(conn: sqlite3.Connection, user_email: str) -> int | None:
    """Ziel-Gewerbe für Share/Mail-Import: eingestelltes Import-Gewerbe des Nutzers,
    sonst das erste aktive Gewerbe."""
    email = user_email.lower()
    row = conn.execute(
        "SELECT import_gewerbe_id FROM user_mail WHERE email = ?", (email,)
    ).fetchone()
    if row and row["import_gewerbe_id"]:
        gid = row["import_gewerbe_id"]
        if conn.execute(
            "SELECT 1 FROM gewerbe WHERE id = ? AND aktiv = 1 "
            "AND (owner_email IS NULL OR owner_email = ?)",
            (gid, email),
        ).fetchone():
            return gid
    row = conn.execute(
        "SELECT id FROM gewerbe WHERE aktiv = 1 AND (owner_email IS NULL OR owner_email = ?) "
        "ORDER BY id LIMIT 1",
        (email,),
    ).fetchone()
    return row["id"] if row else None
