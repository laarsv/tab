"""GiroCode = EPC-QR-Code (European Payments Council, „Quick Response Code: Guidelines to Enable
the Data Capture for the Initiation of a SEPA Credit Transfer", Version 002, UTF-8).

Die Banking-App scannt ihn, die Überweisung ist ausgefüllt: Empfänger, IBAN, Betrag und
Verwendungszweck (die Rechnungsnummer — so findet auch ein späterer Kontoabgleich die Zahlung).

Nie blockieren: Reichen die Angaben nicht (keine/ungültige IBAN, Betrag 0, kein Name), liefert
`epc_payload` None und das PDF kommt ohne Code. Gezeichnet wird als Vektor (scharf beim Druck).
"""
from __future__ import annotations

import re
import sqlite3

import segno

GIRO_MM = 26  # Kantenlänge des Codes im PDF (ohne Ruhezone)
_MAX_CENT = 99_999_999_999  # EPC: höchstens 999.999.999,99 EUR


def iban_normal(iban: str | None) -> str:
    return re.sub(r"\s+", "", iban or "").upper()


def iban_gueltig(iban: str | None) -> bool:
    """Aufbau + Prüfziffer (ISO 7064, mod 97)."""
    i = iban_normal(iban)
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", i):
        return False
    umgestellt = i[4:] + i[:4]
    zahl = "".join(str(int(c, 36)) for c in umgestellt)  # A=10 ... Z=35
    return int(zahl) % 97 == 1


def _zeile(text: str | None, maximal: int) -> str:
    """Einzeilig, Leerraum zusammengezogen, auf die EPC-Feldlänge gekürzt."""
    return " ".join(str(text or "").split())[:maximal]


def absender_name(gewerbe: sqlite3.Row | dict) -> str:
    """Name des Absenders, wie er auf der Rechnung steht: erste Zeile der Rechnungs-Anschrift,
    sonst der interne Gewerbe-Name (der oft nur ein Etikett wie „Makler“ ist)."""
    zeilen = [z.strip() for z in (gewerbe["anschrift"] or "").splitlines() if z.strip()]
    return zeilen[0] if zeilen else (gewerbe["name"] or "")


def kontoinhaber(gewerbe: sqlite3.Row | dict) -> str:
    """Empfängername: ausdrücklich gesetzter Kontoinhaber, sonst der Absendername."""
    return (gewerbe["kontoinhaber"] or "").strip() or absender_name(gewerbe)


def epc_payload(
    *, name: str, iban: str | None, betrag_cent: int, verwendungszweck: str
) -> str | None:
    """EPC-QR-Text (Version 002, Zeichensatz 1 = UTF-8, SEPA-Überweisung) oder None."""
    iban_n = iban_normal(iban)
    if not iban_gueltig(iban_n) or not 1 <= betrag_cent <= _MAX_CENT:
        return None
    empfaenger = _zeile(name, 70)
    if not empfaenger:
        return None
    return "\n".join(
        [
            "BCD",
            "002",
            "1",
            "SCT",
            "",  # BIC: in Version 002 innerhalb des EWR optional
            empfaenger,
            iban_n,
            f"EUR{betrag_cent // 100}.{betrag_cent % 100:02d}",
            "",  # Purpose-Code
            "",  # strukturierte Referenz (nicht zusammen mit Freitext erlaubt)
            _zeile(verwendungszweck, 140),
        ]
    )


def zeichne_qr(pdf, payload: str, x: float, y: float, groesse: float = GIRO_MM) -> None:
    """QR (Fehlerkorrektur M, wie der EPC-Standard verlangt) als schwarze Rechtecke ins PDF.
    Zusammenhängende Module einer Zeile werden zu einem Rechteck, das vermeidet Haarlinien."""
    qr = segno.make(payload, error="m", micro=False, encoding="utf-8", boost_error=False)
    zeilen = [list(z) for z in qr.matrix]
    modul = groesse / len(zeilen)
    pdf.set_fill_color(0, 0, 0)
    for r, zeile in enumerate(zeilen):
        c = 0
        while c < len(zeile):
            if not zeile[c]:
                c += 1
                continue
            start = c
            while c < len(zeile) and zeile[c]:
                c += 1
            # leichte Überlappung nach unten, damit zwischen Zeilen keine Lücke aufblitzt
            pdf.rect(x + start * modul, y + r * modul, (c - start) * modul, modul + 0.02, style="F")


def zeichne_platzhalter(pdf, x: float, y: float, groesse: float = GIRO_MM) -> None:
    """Entwurf: statt des Codes ein leiser Rahmen — ein Entwurf soll nicht bezahlt werden."""
    pdf.set_draw_color(200, 204, 212)
    pdf.rect(x, y, groesse, groesse)
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(110, 115, 125)
    pdf.set_xy(x, y + groesse / 2 - 5)
    pdf.multi_cell(groesse, 3.6, "GiroCode\nin der erstellten\nMahnung", align="C")
