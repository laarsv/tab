"""Gewinnermittlung je Gewerbe und Kalenderjahr: EÜR oder Bilanz (BILANZ.md, Migration v41).

Einzige Quelle für „EÜR oder Bilanz in Jahr X?“: letzter Eintrag in `gewerbe_gewinnermittlung` mit `ab_jahr <= X`, ohne
Eintrag EÜR. Ein Wechsel gilt immer ab dem 1.1. (Muster wie services/besteuerung.py).
"""
from __future__ import annotations

import sqlite3

EUER = "euer"
BILANZ = "bilanz"
ARTEN = (EUER, BILANZ)


def art(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> str:
    r = conn.execute(
        "SELECT art FROM gewerbe_gewinnermittlung WHERE gewerbe_id = ? AND ab_jahr <= ? ORDER BY ab_jahr DESC LIMIT 1",
        (gewerbe_id, jahr),
    ).fetchone()
    return r["art"] if r else EUER


def ist_bilanz(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> bool:
    return art(conn, gewerbe_id, jahr) == BILANZ


def wechsel(conn: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    return [
        {"ab_jahr": r["ab_jahr"], "art": r["art"]}
        for r in conn.execute(
            "SELECT ab_jahr, art FROM gewerbe_gewinnermittlung WHERE gewerbe_id = ? ORDER BY ab_jahr", (gewerbe_id,)
        )
    ]


def erstes_bilanzjahr(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> int | None:
    """Erstes Jahr der zusammenhängenden Bilanz-Periode, zu der `jahr` gehört (für die Eröffnung)."""
    if not ist_bilanz(conn, gewerbe_id, jahr):
        return None
    j = jahr
    while ist_bilanz(conn, gewerbe_id, j - 1) and j > 1900:
        j -= 1
    return j


def bezahlt_markieren(conn: sqlite3.Connection, buchung_id: int, zahltag: str) -> None:
    """Offene Buchung wird bezahlt (Bankumsatz verknüpft): Rechnungsdatum festhalten, Datum = Zahltag."""
    b = conn.execute("SELECT offen, datum, rechnungsdatum FROM buchung WHERE id = ?", (buchung_id,)).fetchone()
    if b is None or not b["offen"]:
        return
    conn.execute(
        "UPDATE buchung SET offen = 0, rechnungsdatum = COALESCE(rechnungsdatum, ?), datum = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (b["datum"], zahltag, buchung_id),
    )
