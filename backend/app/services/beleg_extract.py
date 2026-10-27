"""Beleg-Erkennung: liest Belege aus und schlägt Buchungsfelder vor.

Dreistufige Pipeline (alles lokal, keine Cloud):
1. E-Rechnung: XRechnung-XML (UBL/CII) direkt bzw. ZUGFeRD-XML aus dem PDF —
   exakte Werte (Betrag, Datum, Lieferant, Fälligkeit).
2. PDF mit Textebene: PyMuPDF-Textextraktion, dann Heuristiken.
3. Foto/Scan: Tesseract-OCR (deu) — fehlt das Binary, degradiert die Pipeline
   still (leerer Vorschlag statt Fehler).

Immer nur VORSCHLAG — das UI markiert die Werte zum Prüfen. Kategorie-Vorschlag:
erst lernend (frühere Buchung mit gleichem Lieferanten im Beschreibungstext),
dann Keyword-Liste bekannter Anbieter.
"""
from __future__ import annotations

import datetime as dt
import logging
import re
import sqlite3
import xml.etree.ElementTree as ET

log = logging.getLogger("tab.beleg_extract")

# Keyword -> Kategorie-Key (Reihenfolge = Priorität; nur eindeutige Anbieter).
KEYWORD_KATEGORIEN: list[tuple[str, str]] = [
    # Behörden-Gebühren zuerst: sehr spezifisch. Bewusst KEIN „ordnungsamt"/„bußgeld" —
    # Bußgelder und Verwarnungsgelder sind nicht abziehbar.
    ("verwaltungsgebühr", "gebuehren_abgaben"), ("gebührenbescheid", "gebuehren_abgaben"),
    ("gewerbeanmeldung", "gebuehren_abgaben"), ("gewerbeummeldung", "gebuehren_abgaben"),
    ("gewerbeabmeldung", "gebuehren_abgaben"), ("gewerbemeldestelle", "gebuehren_abgaben"),
    ("hetzner", "software_hosting"), ("netcup", "software_hosting"),
    ("ionos", "software_hosting"), ("strato", "software_hosting"),
    ("adobe", "software_hosting"), ("canva", "software_hosting"),
    ("google workspace", "software_hosting"), ("google cloud", "software_hosting"),
    ("microsoft 365", "software_hosting"), ("apple distribution", "software_hosting"),
    ("developer program", "software_hosting"), ("brevo", "software_hosting"),
    ("openai", "software_hosting"), ("anthropic", "software_hosting"),
    ("github", "software_hosting"),
    ("telekom", "telekommunikation"), ("vodafone", "telekommunikation"),
    ("o2 ", "telekommunikation"), ("telefonica", "telekommunikation"),
    ("1&1", "telekommunikation"), ("congstar", "telekommunikation"),
    ("deutsche bahn", "oepnv"), ("db fernverkehr", "oepnv"), ("db vertrieb", "oepnv"),
    ("flixbus", "oepnv"), ("hvv", "oepnv"), ("bvg", "oepnv"),
    ("deutschlandticket", "oepnv"), ("uber", "oepnv"), ("free now", "oepnv"),
    ("aral", "kfz_kosten"), ("shell", "kfz_kosten"), ("esso", "kfz_kosten"),
    ("jet tankstelle", "kfz_kosten"), ("tankstelle", "kfz_kosten"),
    ("hotel", "reise_nebenkosten"), ("booking.com", "reise_nebenkosten"),
    ("airbnb", "reise_nebenkosten"),
    ("versicherung", "versicherungen_betrieb"), ("allianz", "versicherungen_betrieb"),
    ("hiscox", "versicherungen_betrieb"), ("ihk", "versicherungen_betrieb"),
    ("udemy", "fortbildung"), ("seminar", "fortbildung"),
    ("paypal", "kontogebuehren"), ("stripe", "kontogebuehren"),
    ("deutsche post", "buerobedarf"), ("dhl", "buerobedarf"),
]

# Richtungs-Signale (Einnahme vs. Ausgabe) auf dem Belegtext: Stichwort -> Gewicht.
# Eingang-Belege sind fast immer Ausgaben (Default); Einnahme muss überwiegen.
EINNAHME_SIGNALE: list[tuple[str, int]] = [
    ("provisionsabrechnung", 3), ("courtageabrechnung", 3), ("courtagenabrechnung", 3),
    ("vergütungsabrechnung", 3), ("provisionsgutschrift", 3), ("gutschriftsanzeige", 3),
    ("auszahlungsbeleg", 3), ("auszahlung", 2), ("zahlungsbericht", 3), ("finanzbericht", 3),
    ("payout", 3), ("gutschrift", 2), ("courtage", 1), ("honorar", 1),
]
AUSGABE_SIGNALE: list[tuple[str, int]] = [
    ("bescheid", 3), ("gebührenbescheid", 3), ("mahnung", 3), ("zahlungserinnerung", 3),
    ("zahlbar bis", 3), ("zahlungsbedingungen", 3), ("bitte überweisen", 3),
    ("überweisen sie", 3), ("fällig", 2), ("zu zahlen", 2),
    ("lastschrift", 2), ("abbuchung", 2), ("bestellbestätigung", 2), ("kassenbon", 3),
    ("kassenbeleg", 3), ("tankbeleg", 3), ("verwaltungsgebühr", 3), ("beitragsrechnung", 3),
]

MONATE = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}

BETRAG_RE = re.compile(r"(\d{1,3}(?:\.\d{3})*,\d{2})(?!\d)")
BETRAG_KEYWORDS = ("zu zahlen", "rechnungsbetrag", "gesamtbetrag", "gesamtsumme",
                   "endbetrag", "gesamt", "summe", "total", "brutto", "amount due")
DATUM_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b")
DATUM_ISO_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
DATUM_LANG_RE = re.compile(r"\b(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\s+(\d{4})\b")
FAELLIG_KEYWORDS = ("fällig", "faellig", "zahlbar bis", "zahlungsziel", "due date", "zahlung bis")


def _parse_betrag_cent(s: str) -> int:
    return round(float(s.replace(".", "").replace(",", ".")) * 100)


def _plausibles_datum(j: int, m: int, t: int) -> str | None:
    if j < 100:
        j += 2000
    try:
        d = dt.date(j, m, t)
    except ValueError:
        return None
    heute = dt.date.today()
    if dt.date(heute.year - 6, 1, 1) <= d <= heute + dt.timedelta(days=400):
        return d.isoformat()
    return None


def _datum_in_zeile(zeile: str) -> str | None:
    m = DATUM_RE.search(zeile)
    if m:
        return _plausibles_datum(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    m = DATUM_ISO_RE.search(zeile)
    if m:
        return _plausibles_datum(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = DATUM_LANG_RE.search(zeile)
    if m and m.group(2).lower() in MONATE:
        return _plausibles_datum(int(m.group(3)), MONATE[m.group(2).lower()], int(m.group(1)))
    return None


# ── Stufe 1: E-Rechnung (XRechnung UBL / ZUGFeRD-CII) ──────────────────────────

def _xml_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def parse_e_rechnung(xml_bytes: bytes) -> dict | None:
    """Zieht Betrag/Datum/Lieferant/Fälligkeit aus XRechnung/ZUGFeRD-XML (tolerant,
    über local-names — Namespace-Versionen egal). None, wenn kein Rechnungs-XML."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None
    wurzel = _xml_local(root.tag)
    if wurzel not in ("Invoice", "CrossIndustryInvoice", "CreditNote"):
        return None

    betrag = datum = faellig = lieferant = None
    seller_stack = 0
    for elem in root.iter():
        name = _xml_local(elem.tag)
        text = (elem.text or "").strip()
        if name in ("PayableAmount", "DuePayableAmount") and text and betrag is None:
            try:
                betrag = round(float(text) * 100)
            except ValueError:
                pass
        elif name == "IssueDate" and text and datum is None:
            datum = text[:10]
        elif name == "DueDate" and text and faellig is None:
            faellig = text[:10]
    # CII: Datumsformat 102 (JJJJMMTT) in DateTimeString unterhalb von IssueDateTime etc.
    if wurzel == "CrossIndustryInvoice":
        kontext = None
        for elem in root.iter():
            name = _xml_local(elem.tag)
            if name in ("IssueDateTime", "DueDateDateTime"):
                kontext = name
            elif name == "DateTimeString" and kontext:
                raw = (elem.text or "").strip()
                if len(raw) == 8 and raw.isdigit():
                    iso = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
                    if kontext == "IssueDateTime" and datum is None:
                        datum = iso
                    elif kontext == "DueDateDateTime" and faellig is None:
                        faellig = iso
                kontext = None
    # Lieferant: erster Name unterhalb von SellerTradeParty (CII) bzw.
    # AccountingSupplierParty (UBL).
    def _first_name_unter(container_name: str) -> str | None:
        for elem in root.iter():
            if _xml_local(elem.tag) == container_name:
                for kind in elem.iter():
                    if _xml_local(kind.tag) in ("Name", "RegistrationName"):
                        t = (kind.text or "").strip()
                        if t:
                            return t
        return None

    lieferant = _first_name_unter("SellerTradeParty") or _first_name_unter("AccountingSupplierParty")
    return {
        "quelle": "e-rechnung",
        "betrag_cent": betrag,
        "datum": datum,
        "faellig_am": faellig,
        "lieferant": lieferant,
    }


# ── Stufe 2/3: Text aus PDF (PyMuPDF) oder Bild (Tesseract) ───────────────────

def _text_aus_pdf(path: str) -> tuple[str | None, bytes | None, str]:
    """(text, zugferd_xml, quelle) — zugferd_xml gesetzt, wenn im PDF eingebettet."""
    import fitz  # PyMuPDF

    with fitz.open(path) as doc:
        # ZUGFeRD: eingebettetes Rechnungs-XML?
        for i in range(doc.embfile_count()):
            info = doc.embfile_info(i)
            name = (info.get("filename") or "").lower()
            if name.endswith(".xml"):
                return None, doc.embfile_get(i), "e-rechnung"
        text = "\n".join(page.get_text() for page in doc)
        if len(text.strip()) >= 40:
            return text, None, "pdf-text"
        # Scan ohne Textebene -> OCR über gerenderte Seiten
        try:
            import pytesseract
            from PIL import Image
            import io as _io

            teile = []
            for i in range(min(3, doc.page_count)):
                page = doc[i]
                pix = page.get_pixmap(dpi=200)
                img = Image.open(_io.BytesIO(pix.tobytes("png")))
                teile.append(pytesseract.image_to_string(img, lang="deu"))
            return "\n".join(teile), None, "ocr"
        except Exception as e:
            log.warning("OCR nicht verfügbar/fehlgeschlagen: %s", e)
            return text or None, None, "ocr-fehlgeschlagen"


def _text_aus_bild(path: str) -> tuple[str | None, str]:
    try:
        import pytesseract

        return pytesseract.image_to_string(path, lang="deu"), "ocr"
    except Exception as e:
        log.warning("OCR nicht verfügbar/fehlgeschlagen: %s", e)
        return None, "ocr-fehlgeschlagen"


# ── Heuristiken auf Freitext ──────────────────────────────────────────────────

def _felder_aus_text(text: str) -> dict:
    zeilen = [z.strip() for z in text.splitlines() if z.strip()]
    lower = [z.lower() for z in zeilen]

    betrag = None
    for kw in BETRAG_KEYWORDS:  # Keyword-Priorität: erste Zeile mit Treffer gewinnt
        for z, zl in zip(zeilen, lower):
            if kw in zl:
                treffer = BETRAG_RE.findall(z)
                if treffer:
                    betrag = _parse_betrag_cent(treffer[-1])
                    break
        if betrag is not None:
            break
    if betrag is None:  # Fallback: größter Betrag im Dokument
        alle = [_parse_betrag_cent(m) for m in BETRAG_RE.findall(text)]
        betrag = max(alle) if alle else None

    datum = None
    for z, zl in zip(zeilen, lower):
        if "datum" in zl:  # Rechnungs-/Belegdatum bevorzugen
            datum = _datum_in_zeile(z)
            if datum:
                break
    if datum is None:
        for z in zeilen:
            datum = _datum_in_zeile(z)
            if datum:
                break

    faellig = None
    for z, zl in zip(zeilen, lower):
        if any(kw in zl for kw in FAELLIG_KEYWORDS):
            faellig = _datum_in_zeile(z)
            if faellig:
                break

    lieferant = zeilen[0][:80] if zeilen else None
    return {"betrag_cent": betrag, "datum": datum, "faellig_am": faellig, "lieferant": lieferant}


# ── Richtung (Einnahme/Ausgabe) ───────────────────────────────────────────────

def _eigene_namen(conn: sqlite3.Connection, gewerbe_id: int) -> list[str]:
    """Namen des eigenen Gewerbes (Gewerbename + erste Zeile der Absender-Anschrift)."""
    row = conn.execute(
        "SELECT name, anschrift FROM gewerbe WHERE id = ?", (gewerbe_id,)
    ).fetchone()
    if row is None:
        return []
    namen = [row["name"] or ""]
    if row["anschrift"]:
        namen.append(row["anschrift"].splitlines()[0])
    return [n.strip().lower() for n in namen if len(n.strip()) >= 4]


def _richtung_score(conn: sqlite3.Connection, gewerbe_id: int, text: str,
                    lieferant: str | None, exakt: bool = False) -> int:
    """Positiv = spricht für Einnahme, negativ = für Ausgabe, 0 = keine Signale.

    Ist der Aussteller der eigene Gewerbename, ist es eine eigene Ausgangsrechnung/
    Einnahme. Bei E-Rechnungen (exakt) ist der Verkäufer verlässlich, bei OCR/PDF-Text
    ist „erste Zeile = Lieferant" nur geraten (kann auch die Empfänger-Anschrift sein)
    und zählt daher weniger — ein klares Ausgabe-Stichwort (Bescheid, Mahnung …) gewinnt.
    Dazu Stichworte (Provisions-/Courtage-Abrechnung, Auszahlung, Gutschrift …)
    gegen Ausgabe-Stichworte."""
    lower = text.lower()
    score = 0
    absender = (lieferant or "").strip().lower()
    if len(absender) >= 4 and any(
        n in absender or absender in n for n in _eigene_namen(conn, gewerbe_id)
    ):
        score += 5 if exakt else 3
    score += sum(w for kw, w in EINNAHME_SIGNALE if kw in lower)
    score -= sum(w for kw, w in AUSGABE_SIGNALE if kw in lower)
    return score


# ── Kategorie-Vorschlag ───────────────────────────────────────────────────────

def _kategorie_vorschlag(
    conn: sqlite3.Connection, gewerbe_id: int, text: str, lieferant: str | None,
    typ: str | None = None,
) -> int | None:
    """typ ('einnahme'|'ausgabe') schränkt den Vorschlag auf die erkannte Richtung ein."""
    lower = text.lower()
    typ_sql = " AND k.typ = ?" if typ else ""
    typ_arg = (typ,) if typ else ()
    # 1) Lernend: frühere Buchung, deren Beschreibung den Lieferanten enthält.
    if lieferant:
        token = lieferant.lower().split()[0][:24] if lieferant.split() else ""
        if len(token) >= 4:
            row = conn.execute(
                "SELECT p.kategorie_id FROM buchung b "
                "JOIN buchung_position p ON p.buchung_id = b.id "
                "JOIN kategorie k ON k.id = p.kategorie_id "
                f"WHERE b.gewerbe_id = ? AND lower(b.beschreibung) LIKE ?{typ_sql} "
                "ORDER BY b.datum DESC, b.id DESC LIMIT 1",
                (gewerbe_id, f"%{token}%", *typ_arg),
            ).fetchone()
            if row:
                return row["kategorie_id"]
    # 2) Keyword-Liste bekannter Anbieter.
    for keyword, kat_key in KEYWORD_KATEGORIEN:
        if keyword in lower:
            row = conn.execute(
                f"SELECT k.id FROM kategorie k WHERE k.key = ? AND k.aktiv = 1{typ_sql}",
                (kat_key, *typ_arg),
            ).fetchone()
            if row:
                return row["id"]
    return None


# ── Einstieg ──────────────────────────────────────────────────────────────────

def vorschlag_fuer_beleg(conn: sqlite3.Connection, beleg: sqlite3.Row, pfad: str) -> dict:
    ct = (beleg["content_type"] or "").lower()
    text = None
    ergebnis: dict = {"quelle": "keine", "betrag_cent": None, "datum": None,
                      "faellig_am": None, "lieferant": None, "kategorie_id": None,
                      "richtung": "ausgabe", "richtung_erkannt": False}

    if ct in ("application/xml", "text/xml") or beleg["stored_name"].endswith(".xml"):
        with open(pfad, "rb") as fh:
            parsed = parse_e_rechnung(fh.read())
        if parsed:
            ergebnis.update(parsed)
    elif ct == "application/pdf":
        text, zugferd_xml, quelle = _text_aus_pdf(pfad)
        if zugferd_xml is not None:
            parsed = parse_e_rechnung(zugferd_xml)
            if parsed:
                ergebnis.update(parsed)
        elif text:
            ergebnis.update(_felder_aus_text(text))
            ergebnis["quelle"] = quelle
        else:
            ergebnis["quelle"] = quelle
    else:  # Bild
        text, quelle = _text_aus_bild(pfad)
        if text:
            ergebnis.update(_felder_aus_text(text))
        ergebnis["quelle"] = quelle

    such_text = " ".join(filter(None, [text, ergebnis.get("lieferant"), beleg["original_name"]]))
    lieferant = ergebnis.get("lieferant")

    # Richtung: Textsignale entscheiden; ohne Signal (Score 0) bleibt Ausgabe der Default
    # (Eingang-Belege sind meist Ausgaben), es sei denn eine gelernte Kategorie sagt anders.
    score = _richtung_score(conn, beleg["gewerbe_id"], such_text, lieferant,
                            exakt=ergebnis["quelle"] == "e-rechnung")
    typ = ("einnahme" if score > 0 else "ausgabe") if score != 0 else None
    ergebnis["kategorie_id"] = _kategorie_vorschlag(
        conn, beleg["gewerbe_id"], such_text, lieferant, typ=typ
    )
    if typ:
        ergebnis.update(richtung=typ, richtung_erkannt=True)
    elif ergebnis["kategorie_id"]:
        kat = conn.execute(
            "SELECT typ FROM kategorie WHERE id = ?", (ergebnis["kategorie_id"],)
        ).fetchone()
        if kat:
            ergebnis.update(richtung=kat["typ"], richtung_erkannt=True)
    return ergebnis
