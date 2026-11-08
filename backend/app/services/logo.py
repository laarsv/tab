"""Firmenlogo je Gewerbe: speichern, laden, ins PDF zeichnen.

Das Logo liegt als PNG unter UPLOAD_ROOT/logos/{gewerbe_id}.png (Upload wird geprüft und auf höchstens
LOGO_MAX_PX verkleinert, Transparenz bleibt). Es steht oben rechts auf Rechnung, Mahnung und Angebot.
Das Zeichnen blockiert nie: fehlt die Datei oder ist sie kaputt, kommt das PDF ohne Logo.
"""
from __future__ import annotations

import io
import logging
import os
import sqlite3

from PIL import Image, UnidentifiedImageError

from ..config import settings

log = logging.getLogger("tab.logo")

MAX_LOGO_BYTES = 2 * 1024 * 1024
MAX_EINGANG_PX = 4000   # größere Bilder lehnen wir ab (Dekompressionsbomben)
LOGO_MAX_PX = (900, 360)
ERLAUBT = {"PNG", "JPEG"}


class LogoAbgelehnt(Exception):
    pass


def _verzeichnis() -> str:
    return os.path.join(settings.UPLOAD_ROOT, "logos")


def logo_pfad(gewerbe: sqlite3.Row | dict) -> str | None:
    """Absoluter Pfad des Logos oder None. Nur der Dateiname aus der DB zählt (kein Pfadanteil)."""
    if "logo_datei" not in (gewerbe.keys() if hasattr(gewerbe, "keys") else gewerbe):
        return None
    name = gewerbe["logo_datei"]
    if not name or os.path.basename(name) != name:
        return None
    pfad = os.path.join(_verzeichnis(), name)
    return pfad if os.path.isfile(pfad) else None


def speichere_logo(conn: sqlite3.Connection, gewerbe_id: int, data: bytes) -> str:
    if not data:
        raise LogoAbgelehnt("Die Datei ist leer.")
    if len(data) > MAX_LOGO_BYTES:
        raise LogoAbgelehnt(f"Datei zu groß (höchstens {MAX_LOGO_BYTES // (1024 * 1024)} MB).")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        if fmt not in ERLAUBT:
            raise LogoAbgelehnt("Nur PNG oder JPG.")
        if max(img.size) > MAX_EINGANG_PX:
            raise LogoAbgelehnt(f"Das Bild ist zu groß (höchstens {MAX_EINGANG_PX} Pixel je Seite).")
        img.load()
    except LogoAbgelehnt:
        raise
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise LogoAbgelehnt("Das ist keine lesbare Bilddatei (PNG oder JPG).")
    img = img.convert("RGBA")
    img.thumbnail(LOGO_MAX_PX)
    os.makedirs(_verzeichnis(), exist_ok=True)
    name = f"{gewerbe_id}.png"
    img.save(os.path.join(_verzeichnis(), name), format="PNG", optimize=True)
    conn.execute("UPDATE gewerbe SET logo_datei = ?, updated_at = datetime('now') WHERE id = ?", (name, gewerbe_id))
    return name


def loesche_logo(conn: sqlite3.Connection, gewerbe_id: int) -> None:
    row = conn.execute("SELECT logo_datei FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    conn.execute("UPDATE gewerbe SET logo_datei = NULL, updated_at = datetime('now') WHERE id = ?", (gewerbe_id,))
    if row and row["logo_datei"] and os.path.basename(row["logo_datei"]) == row["logo_datei"]:
        try:
            os.remove(os.path.join(_verzeichnis(), row["logo_datei"]))
        except OSError:
            pass


def zeichne_logo(pdf, gewerbe, *, rechts: float = 190, oben: float = 8, max_b: float = 50, max_h: float = 17) -> None:
    """Logo oben rechts, in die Box max_b × max_h einpassen. Nie blockierend."""
    try:
        pfad = logo_pfad(gewerbe)
        if not pfad:
            return
        with Image.open(pfad) as img:
            b, h = img.size
        faktor = min(max_b / b, max_h / h)
        breite, hoehe = b * faktor, h * faktor
        pdf.image(pfad, x=rechts - breite, y=oben, w=breite, h=hoehe)
    except Exception:
        log.exception("Logo konnte nicht ins PDF gezeichnet werden")
