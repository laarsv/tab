"""Gemeinsame Rechnungs-Erstellung — genutzt von routes/rechnungen.py (manuell)
und services/abo.py (wiederkehrende Rechnungen). Nummer: fortlaufend je
Gewerbe + Jahr ({jahr}-{lauf:04d}), Jahr aus dem Rechnungsdatum."""
from __future__ import annotations

import sqlite3

from .fristen import faelligkeit


def standard_zahlungsziel(conn: sqlite3.Connection, gewerbe_id: int) -> int:
    row = conn.execute(
        "SELECT zahlungsziel_tage FROM gewerbe WHERE id = ?", (gewerbe_id,)
    ).fetchone()
    return row["zahlungsziel_tage"] if row else 14


def erstelle_rechnung(
    conn: sqlite3.Connection,
    *,
    gewerbe_id: int,
    datum: str,
    leistungsdatum: str | None,
    empfaenger_name: str,
    empfaenger_anschrift: str | None,
    empfaenger_email: str | None,
    notiz: str | None,
    steuerhinweis: str,
    positionen: list[dict],  # {beschreibung, menge, einzelpreis_cent}
    zahlungsziel_tage: int | None = None,  # None = Standard-Zahlungsziel des Gewerbes
) -> int:
    """Legt Rechnung + Positionen an (ohne Commit) und gibt die Rechnungs-ID zurück."""
    jahr = int(datum[:4])
    if zahlungsziel_tage is None:
        zahlungsziel_tage = standard_zahlungsziel(conn, gewerbe_id)
    lauf = (
        conn.execute(
            "SELECT COALESCE(MAX(laufnummer), 0) FROM rechnung WHERE gewerbe_id = ? AND jahr = ?",
            (gewerbe_id, jahr),
        ).fetchone()[0]
        + 1
    )
    cur = conn.execute(
        """
        INSERT INTO rechnung (gewerbe_id, jahr, laufnummer, nummer, datum, leistungsdatum,
                              empfaenger_name, empfaenger_anschrift, empfaenger_email, notiz,
                              steuerhinweis, zahlungsziel_tage, faellig_am)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gewerbe_id,
            jahr,
            lauf,
            f"{jahr}-{lauf:04d}",
            datum,
            (leistungsdatum or "").strip() or None,
            empfaenger_name.strip(),
            (empfaenger_anschrift or "").strip() or None,
            (empfaenger_email or "").strip() or None,
            (notiz or "").strip() or None,
            steuerhinweis,
            zahlungsziel_tage,
            faelligkeit(datum, zahlungsziel_tage),
        ),
    )
    rid = cur.lastrowid
    conn.executemany(
        "INSERT INTO rechnung_position (rechnung_id, beschreibung, menge, einzelpreis_cent) "
        "VALUES (?, ?, ?, ?)",
        [
            (rid, p["beschreibung"].strip(), p["menge"], p["einzelpreis_cent"])
            for p in positionen
        ],
    )
    return rid
