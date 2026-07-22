"""Gemeinsame Rechnungs-Erstellung — genutzt von routes/rechnungen.py (manuell)
und services/abo.py (wiederkehrende Rechnungen). Nummer: fortlaufend je
Gewerbe + Jahr ({jahr}-{lauf:04d}), Jahr aus dem Rechnungsdatum."""
from __future__ import annotations

import sqlite3


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
) -> int:
    """Legt Rechnung + Positionen an (ohne Commit) und gibt die Rechnungs-ID zurück."""
    jahr = int(datum[:4])
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
                              steuerhinweis)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
