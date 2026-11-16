"""Besteuerung je Gewerbe und Kalenderjahr (EUER_KATEGORIEN.md §8, Migration v34).

Einzige Quelle für die Frage „Kleinunternehmer oder Regelbesteuerung in Jahr X?“: der letzte Eintrag in
`gewerbe_besteuerung` mit `ab_jahr <= X`, ohne Eintrag Kleinunternehmer. Ein Wechsel gilt immer ab dem 1.1.
`gewerbe.besteuerung` wird nur als „aktueller Stand“ für Anzeige/MCP mitgeführt (`sync_aktuell`).
"""
from __future__ import annotations

import datetime as dt
import sqlite3

KU = "kleinunternehmer"
REGEL = "regelbesteuerung"
ARTEN = (KU, REGEL)
# Zahlungen ans/vom Finanzamt: selbst Steuer, haben keinen Steuersatz
OHNE_SATZ = {"ust_zahlung", "ust_erstattung"}


def art(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> str:
    r = conn.execute(
        "SELECT art FROM gewerbe_besteuerung WHERE gewerbe_id = ? AND ab_jahr <= ? ORDER BY ab_jahr DESC LIMIT 1",
        (gewerbe_id, jahr),
    ).fetchone()
    return r["art"] if r else KU


def ist_regel(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> bool:
    return art(conn, gewerbe_id, jahr) == REGEL


def art_zum_datum(conn: sqlite3.Connection, gewerbe_id: int, datum: str) -> str:
    return art(conn, gewerbe_id, int(datum[:4]))


def wechsel(conn: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    return [
        {"ab_jahr": r["ab_jahr"], "art": r["art"]}
        for r in conn.execute(
            "SELECT ab_jahr, art FROM gewerbe_besteuerung WHERE gewerbe_id = ? ORDER BY ab_jahr", (gewerbe_id,)
        )
    ]


def je_jahr(conn: sqlite3.Connection, gewerbe_id: int, jahre: list[int]) -> dict[str, str]:
    return {str(j): art(conn, gewerbe_id, j) for j in jahre}


def sync_aktuell(conn: sqlite3.Connection, gewerbe_id: int) -> None:
    """`gewerbe.besteuerung` = Stand im laufenden Jahr (nur Anzeige; gerechnet wird mit `art`)."""
    neu = art(conn, gewerbe_id, dt.date.today().year)
    conn.execute("UPDATE gewerbe SET besteuerung = ? WHERE id = ? AND besteuerung IS NOT ?", (neu, gewerbe_id, neu))


def sync_alle(conn: sqlite3.Connection) -> None:
    """Beim Start: Jahreswechsel nachziehen (schreibt nur, wenn sich der Stand geändert hat)."""
    for r in conn.execute("SELECT id FROM gewerbe").fetchall():
        sync_aktuell(conn, r["id"])
    conn.commit()


def ust_aus_brutto(brutto_cent: int, ust_bp: int) -> int:
    """Steuer, die in einem Bruttobetrag steckt: brutto × Satz / (100 % + Satz), kaufmännisch gerundet."""
    if not ust_bp or brutto_cent <= 0:
        return 0
    zaehler = brutto_cent * ust_bp
    nenner = 10000 + ust_bp
    return (2 * zaehler + nenner) // (2 * nenner)


def ust_auf_netto(netto_cent: int, ust_bp: int) -> int:
    """Steuer auf einen Nettobetrag, kaufmännisch gerundet (Rechnungen, je Satz auf die Netto-Summe)."""
    if not ust_bp:
        return 0
    zaehler = netto_cent * ust_bp
    vz = -1 if zaehler < 0 else 1
    return vz * ((2 * abs(zaehler) + 10000) // 20000)
