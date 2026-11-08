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
from .mahnwesen import summe_cent

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
    """Versendete, noch nicht bezahlte Rechnungen mit Summe."""
    return [
        {
            "id": r["id"], "nummer": r["nummer"], "empfaenger_name": r["empfaenger_name"], "datum": r["datum"],
            "faellig_am": r["faellig_am"], "summe_cent": summe_cent(conn, r["id"]), "steuerhinweis": r["steuerhinweis"],
        }
        for r in conn.execute(
            "SELECT * FROM rechnung WHERE gewerbe_id = ? AND status = 'versendet' ORDER BY datum, id", (gewerbe_id,)
        )
    ]


def rechnung_treffer(offen: list[dict], u: dict) -> list[dict]:
    """Offene Rechnungen für einen Eingang, beste zuerst (ab SCHWELLE Punkten)."""
    if u["betrag_cent"] <= 0:
        return []
    text = _norm(f"{u['verwendungszweck'] or ''} {u['referenz'] or ''}")
    treffer = []
    for r in offen:
        punkte, gruende = 0, []
        if r["summe_cent"] == u["betrag_cent"]:
            punkte += 50
            gruende.append("Betrag stimmt exakt")
        if _norm(r["nummer"]) and _norm(r["nummer"]) in text:
            punkte += 40
            gruende.append("Rechnungsnummer im Verwendungszweck")
        if _name_passt(r["empfaenger_name"], u["gegenpartei"], u["verwendungszweck"]):
            punkte += 15
            gruende.append("Name passt")
        if punkte >= SCHWELLE:
            treffer.append({**r, "punkte": punkte, "gruende": gruende})
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


def alle_offenen_belege(conn: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    return [
        {"id": b["id"], "original_name": b["original_name"], "faellig_am": b["faellig_am"], "created_at": b["created_at"]}
        for b in conn.execute(
            "SELECT * FROM beleg WHERE gewerbe_id = ? AND buchung_id IS NULL ORDER BY created_at DESC LIMIT 100",
            (gewerbe_id,),
        )
    ]
