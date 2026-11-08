"""Zuordnungsvorschläge für Bankumsätze — mit Begründung, immer nur Vorschlag.

Aufbau nach Haben (Punkte je Grund, Vorschlag erst ab 40 Punkten, Treffer mit Gründen), Werte und
Code eigenständig. Eingang → offene Rechnungen; Ausgang → Kategorie (aus früheren Buchungen
gelernt) und offene Eingangs-Belege mit lesbarem Betrag.

  Betrag stimmt exakt            50
  Rechnungsnummer im Zweck       40
  Name/Lieferant passt           15
  Belegdatum passend (≤ 90 T.)   10    nur Belege
  Fälligkeit am Umsatztag        10    nur Belege
"""
from __future__ import annotations

import datetime as dt
import os
import re
import sqlite3

from ..config import settings
from .beleg_extract import _kategorie_vorschlag, vorschlag_fuer_beleg
from . import dauerbelege, zahlungen

SCHWELLE = 40
RECHTSFORMEN = {"gmbh", "mbh", "ag", "ug", "kg", "ohg", "gbr", "se", "co", "ev", "eg", "kgaa", "ltd", "inc"}
MAX_BELEGE_PRUEFEN = 25


def _norm(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def _woerter(text: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-zäöüß]{3,}", (text or "").lower()) if w not in RECHTSFORMEN}


def _name_passt(a: str | None, *andere: str | None) -> bool:
    return bool(_woerter(a) & _woerter(" ".join(x or "" for x in andere)))


def offene_rechnungen(conn: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    """Versendete Rechnungen, auf denen noch etwas offen ist (nach Teilzahlungen/Skonto)."""
    out = []
    for r in conn.execute(
        "SELECT * FROM rechnung WHERE gewerbe_id = ? AND status = 'versendet' ORDER BY datum, id", (gewerbe_id,)
    ):
        st = zahlungen.stand(conn, r)
        if st["offen_cent"] <= 0:
            continue
        # Skonto nur auf die ganze, noch unberührte Rechnung (wie Haben)
        sk = zahlungen.skonto_cent(st["summe_cent"], r["skonto_bp"]) if not st["zahlungen"] else 0
        out.append(
            {
                "id": r["id"], "nummer": r["nummer"], "empfaenger_name": r["empfaenger_name"], "datum": r["datum"],
                "faellig_am": r["faellig_am"], "summe_cent": st["summe_cent"], "offen_cent": st["offen_cent"],
                "steuerhinweis": r["steuerhinweis"], "skonto_bp": r["skonto_bp"] if sk else None,
                "skonto_tage": r["skonto_tage"] if sk else None, "skonto_cent": sk,
                "skonto_bis": zahlungen.skonto_bis(r["datum"], r["skonto_tage"]) if sk else None,
            }
        )
    return out


def rechnung_treffer(offen: list[dict], u: dict) -> list[dict]:
    """Offene Rechnungen für einen Eingang, beste zuerst (ab SCHWELLE Punkten)."""
    if u["betrag_cent"] <= 0:
        return []
    text = _norm(f"{u['verwendungszweck'] or ''} {u['referenz'] or ''}")
    treffer = []
    for r in offen:
        punkte, gruende, skonto_match = 0, [], False
        if r["offen_cent"] == u["betrag_cent"]:
            punkte += 50
            gruende.append("Betrag stimmt exakt")
        elif r["skonto_cent"] and r["offen_cent"] - r["skonto_cent"] == u["betrag_cent"] and zahlungen.skonto_gilt(r, u["datum"]):
            punkte += 50
            skonto_match = True
            gruende.append(f"Betrag mit {r['skonto_bp'] / 100:.2f} % Skonto".replace(".", ",") + ", in der Frist")
        elif 0 < u["betrag_cent"] < r["offen_cent"]:
            punkte += 5
            gruende.append("Teilbetrag des offenen Betrags")
        if _norm(r["nummer"]) and _norm(r["nummer"]) in text:
            punkte += 40
            gruende.append("Rechnungsnummer im Verwendungszweck")
        if _name_passt(r["empfaenger_name"], u["gegenpartei"], u["verwendungszweck"]):
            punkte += 15
            gruende.append("Name passt")
        if punkte >= SCHWELLE:
            treffer.append({**r, "punkte": punkte, "gruende": gruende, "skonto_match": skonto_match})
    treffer.sort(key=lambda t: (-t["punkte"], t["datum"]))
    return treffer


def kategorie_vorschlag(conn: sqlite3.Connection, u: dict) -> int | None:
    typ = "einnahme" if u["betrag_cent"] > 0 else "ausgabe"
    text = f"{u['gegenpartei'] or ''} {u['verwendungszweck'] or ''}"
    return _kategorie_vorschlag(conn, u["gewerbe_id"], text, u["gegenpartei"] or None, typ=typ)


def beleg_treffer(conn: sqlite3.Connection, u: dict) -> list[dict]:
    """Offene Eingangs-Belege (PDF/XML, bei Bildern wäre OCR zu langsam) mit passendem Betrag."""
    if u["betrag_cent"] >= 0:
        return []
    betrag = -u["betrag_cent"]
    heute = dt.date.fromisoformat(u["datum"])
    treffer = []
    belege = conn.execute(
        "SELECT * FROM beleg WHERE gewerbe_id = ? AND buchung_id IS NULL AND content_type != 'image/jpeg' "
        "AND content_type != 'image/png' ORDER BY created_at DESC LIMIT ?",
        (u["gewerbe_id"], MAX_BELEGE_PRUEFEN),
    ).fetchall()
    for b in belege:
        pfad = os.path.join(settings.UPLOAD_ROOT, b["stored_name"])
        if not os.path.exists(pfad):
            continue
        try:
            v = vorschlag_fuer_beleg(conn, b, pfad)
        except Exception:
            continue
        punkte, gruende = 0, []
        if v.get("betrag_cent") == betrag:
            punkte += 50
            gruende.append("Betrag stimmt exakt")
        if _name_passt(v.get("lieferant"), u["gegenpartei"], u["verwendungszweck"]):
            punkte += 15
            gruende.append("Lieferant passt")
        try:
            belegdatum = dt.date.fromisoformat(v["datum"]) if v.get("datum") else None
            if belegdatum and 0 <= (heute - belegdatum).days <= 90:
                punkte += 10
                gruende.append("Belegdatum passt")
            faellig = dt.date.fromisoformat(b["faellig_am"] or v["faellig_am"]) if (b["faellig_am"] or v.get("faellig_am")) else None
            if faellig and abs((heute - faellig).days) <= 3:
                punkte += 10
                gruende.append("Fälligkeit passt")
        except (ValueError, TypeError):
            pass
        if punkte >= SCHWELLE:
            treffer.append(
                {"id": b["id"], "original_name": b["original_name"], "lieferant": v.get("lieferant"),
                 "betrag_cent": v.get("betrag_cent"), "datum": v.get("datum"), "punkte": punkte, "gruende": gruende}
            )
    treffer.sort(key=lambda t: -t["punkte"])
    return treffer[:3]


SCHWELLE_BUCHUNG = 60
BUCHUNG_FENSTER_TAGE = 14


def buchung_treffer(conn: sqlite3.Connection, u: dict) -> list[dict]:
    """Schon gebuchte Buchungen, zu denen dieser Umsatz gehört (z. B. ein Termin, den du auf der
    Dauerbeleg-Seite gebucht hast, bevor der Kontoauszug kam): Summe gleich dem Umsatzbetrag (50), Datum
    binnen 14 Tagen (10, binnen 3 Tagen 20) und Beschreibung passt (30) — ab 60 Punkten. Nur Buchungen, die
    noch an keinem Umsatz hängen und deren Positionen alle die Richtung des Umsatzes haben."""
    betrag = abs(u["betrag_cent"])
    typ = "einnahme" if u["betrag_cent"] > 0 else "ausgabe"
    tag = dt.date.fromisoformat(u["datum"])
    von = (tag - dt.timedelta(days=BUCHUNG_FENSTER_TAGE)).isoformat()
    bis = (tag + dt.timedelta(days=BUCHUNG_FENSTER_TAGE)).isoformat()
    treffer = []
    for b in conn.execute(
        """
        SELECT b.id, b.datum, b.beschreibung, SUM(p.betrag_cent) AS summe,
               GROUP_CONCAT(DISTINCT k.name) AS kategorien
        FROM buchung b
        JOIN buchung_position p ON p.buchung_id = b.id
        JOIN kategorie k ON k.id = p.kategorie_id
        WHERE b.gewerbe_id = ? AND b.datum BETWEEN ? AND ?
          AND NOT EXISTS (SELECT 1 FROM bank_umsatz x WHERE x.buchung_id = b.id)
        GROUP BY b.id
        HAVING SUM(p.betrag_cent) = ? AND SUM(CASE WHEN k.typ = ? THEN 0 ELSE 1 END) = 0
        """,
        (u["gewerbe_id"], von, bis, betrag, typ),
    ):
        abstand = abs((dt.date.fromisoformat(b["datum"]) - tag).days)
        punkte, gruende = 50, ["Betrag stimmt exakt"]
        punkte += 20 if abstand <= 3 else 10
        gruende.append("Datum passt" if abstand <= 3 else f"{abstand} Tage Abstand")
        if _name_passt(b["beschreibung"], u["gegenpartei"], u["verwendungszweck"]):
            punkte += 30
            gruende.append("Beschreibung passt")
        if punkte >= SCHWELLE_BUCHUNG:
            treffer.append(
                {"id": b["id"], "datum": b["datum"], "beschreibung": b["beschreibung"], "summe_cent": b["summe"],
                 "kategorien": b["kategorien"], "punkte": punkte, "gruende": gruende}
            )
    treffer.sort(key=lambda t: (-t["punkte"], t["datum"]))
    return treffer[:3]


SCHWELLE_DAUERBELEG = 70


def dauerbeleg_treffer(conn: sqlite3.Connection, u: dict) -> list[dict]:
    """Dauerbelege, deren nächster Termin zu dieser Abbuchung passt: Betrag exakt (50) plus Bezeichnung im
    Verwendungszweck (30) und/oder Termin binnen 7 Tagen (20) — erst ab 70 Punkten. Tab bucht nie von selbst:
    „Buchen“ öffnet das Buchungsfenster, das den Umsatz und den Termin zusammen verbucht."""
    if u["betrag_cent"] >= 0:
        return []
    betrag = -u["betrag_cent"]
    tag = dt.date.fromisoformat(u["datum"])
    treffer = []
    for d in conn.execute(
        "SELECT d.*, k.name AS kategorie_name FROM dauerbeleg d JOIN kategorie k ON k.id = d.kategorie_id "
        "WHERE d.gewerbe_id = ? AND d.aktiv = 1 AND d.betrag_cent = ?",
        (u["gewerbe_id"], betrag),
    ):
        if dauerbelege.ist_beendet(d):
            continue
        termin = dt.date.fromisoformat(d["naechste_am"])
        if (termin - tag).days > 10:  # Termin liegt noch weit nach der Abbuchung
            continue
        punkte, gruende = 50, ["Betrag stimmt exakt"]
        if _name_passt(d["bezeichnung"], u["gegenpartei"], u["verwendungszweck"]):
            punkte += 30
            gruende.append("Bezeichnung passt")
        if abs((termin - tag).days) <= 7:
            punkte += 20
            gruende.append("Termin passt")
        if punkte >= SCHWELLE_DAUERBELEG:
            treffer.append(
                {"id": d["id"], "bezeichnung": d["bezeichnung"], "kategorie_id": d["kategorie_id"],
                 "kategorie_name": d["kategorie_name"], "betrag_cent": d["betrag_cent"], "privat_bp": d["privat_bp"],
                 "termin": d["naechste_am"], "punkte": punkte, "gruende": gruende}
            )
    treffer.sort(key=lambda t: -t["punkte"])
    return treffer[:3]


def alle_offenen_belege(conn: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    return [
        {"id": b["id"], "original_name": b["original_name"], "faellig_am": b["faellig_am"], "created_at": b["created_at"]}
        for b in conn.execute(
            "SELECT * FROM beleg WHERE gewerbe_id = ? AND buchung_id IS NULL ORDER BY created_at DESC LIMIT 100",
            (gewerbe_id,),
        )
    ]
