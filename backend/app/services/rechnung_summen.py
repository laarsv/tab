"""Summen von Rechnungen und Angeboten — die einzige Stelle, die Positionen zu Beträgen rechnet.

Kleinunternehmer: alle Positionen ohne Steuersatz, Summe = Σ round(menge × einzelpreis) wie bisher (brutto).
Regelbesteuerung (EUER_KATEGORIEN.md §8): Positionspreise sind NETTO; je Steuersatz wird die Netto-Summe
gebildet und die Steuer darauf kaufmännisch gerundet (EN 16931: Steuer je Satz auf die Summe, nicht je Zeile).
Brutto = Netto + Steuer. Diese Bruttosumme ist der Rechnungsbetrag für Zahlungen, Mahnwesen, GiroCode und Bank.
"""
from __future__ import annotations

import sqlite3

from . import besteuerung as best


def zeile_netto(menge: float, einzelpreis_cent: int) -> int:
    return round(menge * einzelpreis_cent)


def summen(positionen) -> dict:
    """`positionen`: Folge von Zeilen/Dicts mit menge, einzelpreis_cent und optional ust_bp."""
    je_satz: dict[int, int] = {}
    for p in positionen:
        satz = (p["ust_bp"] if _hat(p, "ust_bp") else 0) or 0
        je_satz[satz] = je_satz.get(satz, 0) + zeile_netto(p["menge"], p["einzelpreis_cent"])
    gruppen = [
        {"ust_bp": satz, "netto_cent": netto, "ust_cent": best.ust_auf_netto(netto, satz)}
        for satz, netto in sorted(je_satz.items(), key=lambda x: -x[0])
    ]
    for g in gruppen:
        g["brutto_cent"] = g["netto_cent"] + g["ust_cent"]
    netto = sum(g["netto_cent"] for g in gruppen)
    ust = sum(g["ust_cent"] for g in gruppen)
    return {
        "netto_cent": netto,
        "ust_cent": ust,
        "brutto_cent": netto + ust,
        "je_satz": gruppen,
        "mit_ust": any(g["ust_bp"] for g in gruppen),
    }


def _hat(p, key: str) -> bool:
    try:
        return key in p.keys()
    except AttributeError:
        return key in p


def rechnung(conn: sqlite3.Connection, rechnung_id: int) -> dict:
    return summen(
        conn.execute("SELECT menge, einzelpreis_cent, ust_bp FROM rechnung_position WHERE rechnung_id = ?", (rechnung_id,))
        .fetchall()
    )


def zahlung_positionen(conn: sqlite3.Connection, rechnung_row, betrag_cent: int, datum: str) -> list[dict]:
    """Einnahme-Positionen für eine Zahlung auf eine Rechnung: anteilig je Steuersatz.

    Kleinunternehmer-Jahr (Zahlungsdatum): eine Position wie bisher (`einnahme_ku` bzw. `einnahme_steuerfrei` bei
    Hinweis § 4 Nr. 11), ohne Steuer. Regelbesteuerung: je Satz ein Anteil am gezahlten Betrag (nach Brutto-Anteil,
    Rest auf den letzten), Steuer anteilig aus der Steuer des Satzes; Satz > 0 → `einnahme_ust`, 0 % →
    `einnahme_steuerfrei`. Liefert [{kategorie_id, kategorie_key, betrag_cent, ust_bp, ust_cent}]."""
    ids = {r["key"]: r["id"] for r in conn.execute("SELECT id, key FROM kategorie")}
    if best.art_zum_datum(conn, rechnung_row["gewerbe_id"], datum) == best.KU:
        key = "einnahme_steuerfrei" if rechnung_row["steuerhinweis"] == "vers4nr11" else "einnahme_ku"
        return [{"kategorie_id": ids[key], "kategorie_key": key, "betrag_cent": betrag_cent, "ust_bp": 0, "ust_cent": 0}]
    s = rechnung(conn, rechnung_row["id"])
    gruppen = [g for g in s["je_satz"] if g["brutto_cent"] > 0] or [{"ust_bp": 0, "brutto_cent": 1, "ust_cent": 0}]
    gesamt = sum(g["brutto_cent"] for g in gruppen)
    out, verteilt = [], 0
    for i, g in enumerate(gruppen):
        anteil = betrag_cent - verteilt if i == len(gruppen) - 1 else round(betrag_cent * g["brutto_cent"] / gesamt)
        verteilt += anteil
        if anteil <= 0:
            continue
        ust = round(g["ust_cent"] * anteil / g["brutto_cent"]) if g["ust_bp"] else 0
        key = "einnahme_ust" if g["ust_bp"] else "einnahme_steuerfrei"
        out.append({"kategorie_id": ids[key], "kategorie_key": key, "betrag_cent": anteil,
                    "ust_bp": g["ust_bp"] if ust else 0, "ust_cent": ust})
    return out


class SteuerFehler(ValueError):
    """Positionen/Steuerhinweis passen nicht zur Besteuerung im Jahr des Rechnungsdatums."""


def pruefe_steuer(conn: sqlite3.Connection, gewerbe_id: int, datum: str, steuerhinweis: str, positionen) -> str:
    """Prüft Steuersätze und Steuerhinweis einer Rechnung/eines Angebots und gibt den passenden Hinweis zurück.

    Kleinunternehmer-Jahr: kein Steuersatz; Hinweis `ku19` oder `vers4nr11` (`regel` wird zu `ku19`).
    Regelbesteuerung: Sätze 0/7/19 %; `ku19` wird zu `regel` (kein Hinweistext). Gibt es 0-%-Positionen, braucht
    die Rechnung einen Grund dafür (`vers4nr11`), sonst SteuerFehler."""
    saetze = [(p["ust_bp"] if isinstance(p, dict) else getattr(p, "ust_bp", 0)) or 0 for p in positionen]
    if any(s not in (0, 700, 1900) for s in saetze):
        raise SteuerFehler("Steuersatz muss 19 %, 7 % oder 0 % sein.")
    if best.art_zum_datum(conn, gewerbe_id, datum) == best.KU:
        if any(saetze):
            raise SteuerFehler("Als Kleinunternehmer weist die Rechnung keine Umsatzsteuer aus — Steuersätze entfernen.")
        return "ku19" if steuerhinweis == "regel" else steuerhinweis
    hinweis = "regel" if steuerhinweis == "ku19" else steuerhinweis
    if hinweis == "regel" and any(s == 0 for s in saetze):
        raise SteuerFehler(
            "Positionen ohne Umsatzsteuer brauchen einen Grund auf der Rechnung — als Steuerhinweis § 4 Nr. 11 wählen "
            "oder einen Steuersatz setzen."
        )
    return hinweis
