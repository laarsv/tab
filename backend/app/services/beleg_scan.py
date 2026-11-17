"""Belegscanner: fotografierte Seiten (JPG/PNG) zu EINER PDF zusammenfügen.

Die Aufbereitung (Zuschnitt, Entzerren, Kontrast, Verkleinern) passiert im Browser
(`frontend/src/lib/scan.js`); hier wird nur geprüft und zusammengesetzt. Jede Seite
bekommt die Breite einer A4-Seite (595 pt), die Höhe folgt dem Seitenverhältnis des
Bildes — so druckt die PDF ordentlich und die OCR (`beleg_extract._text_aus_pdf`)
liest die Seiten wie einen Scan ohne Textebene."""
from __future__ import annotations

import io

MAX_SEITEN = 30
SEITE_BREITE_PT = 595.0  # A4-Breite


class ScanAbgelehnt(Exception):
    """Seiten nicht verwendbar — Meldung ist nutzertauglich."""


def _bild_pruefen(data: bytes, nr: int) -> tuple[bytes, int, int]:
    """Prüft eine Seite mit Pillow und liefert (Bilddaten, Breite, Höhe).
    PNG mit Transparenz und andere Modi werden als JPEG neu kodiert."""
    from PIL import Image, ImageOps

    if not data:
        raise ScanAbgelehnt(f"Seite {nr} ist leer.")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        if fmt not in ("JPEG", "PNG"):
            raise ScanAbgelehnt(f"Seite {nr}: nur JPG oder PNG möglich.")
        # Drehung aus den EXIF-Daten anwenden (Kamera-Fotos direkt vom Handy).
        dreht = img.getexif().get(0x0112, 1) not in (None, 1)
        gedreht = ImageOps.exif_transpose(img) if dreht else img
        if dreht or img.mode not in ("RGB", "L") or fmt != "JPEG":
            gedreht = gedreht.convert("L" if gedreht.mode in ("L", "LA", "1") else "RGB")
            buf = io.BytesIO()
            gedreht.save(buf, "JPEG", quality=85, optimize=True)
            data = buf.getvalue()
        return data, gedreht.width, gedreht.height
    except ScanAbgelehnt:
        raise
    except Exception:
        raise ScanAbgelehnt(f"Seite {nr} ist kein lesbares Bild.")


def bilder_zu_pdf(seiten: list[bytes]) -> bytes:
    """Fügt die Seiten in der gegebenen Reihenfolge zu einer PDF zusammen."""
    import fitz  # PyMuPDF

    if not seiten:
        raise ScanAbgelehnt("Keine Seite aufgenommen.")
    if len(seiten) > MAX_SEITEN:
        raise ScanAbgelehnt(f"Höchstens {MAX_SEITEN} Seiten je Beleg.")
    doc = fitz.open()
    try:
        for nr, data in enumerate(seiten, start=1):
            bild, breite, hoehe = _bild_pruefen(data, nr)
            hoehe_pt = SEITE_BREITE_PT * hoehe / max(breite, 1)
            page = doc.new_page(width=SEITE_BREITE_PT, height=hoehe_pt)
            page.insert_image(page.rect, stream=bild)
        doc.set_metadata({"producer": "Tab Belegscanner", "creator": "Tab Belegscanner"})
        return doc.tobytes(garbage=3, deflate=True)
    finally:
        doc.close()
