"""Kennzahlen eines Gewerbes in einem Jahr — gemeinsam für die Buchungen-Seite und die Übersicht."""
from __future__ import annotations

import sqlite3

from . import besteuerung as best
from .privatanteil import BETRIEBLICH_SQL, BETRIEBLICH_UST_SQL

# §19 UStG Kleinunternehmer-Grenzen (brutto), in Cent.
KU_GRENZE_VORJAHR_CENT = 25_000_00
KU_GRENZE_LAUFEND_CENT = 100_000_00


def summen(db: sqlite3.Connection, gewerbe_id: int, jahr: int) -> dict:
    """Einnahmen, Ausgaben (nur der betriebliche Teil) und KU-Umsatz in Cent.

    ku_umsatz: Gesamtumsatz i. S. d. §19 Abs. 2 UStG — steuerfreie Umsätze nach §4 Nr. 11 (Courtage)
    und Verkäufe von Anlagevermögen bleiben außer Ansatz.

    Einnahmen/Ausgaben sind Zahlungsflüsse (brutto, betrieblicher Teil). Bei Regelbesteuerung ist das nach der
    EÜR-Ist-Versteuerung auch der Gewinn (vereinnahmte USt ist Einnahme, Vorsteuer Ausgabe); `ust_cent` und
    `vorsteuer_cent` zeigen die enthaltene Steuer, `besteuerung` die Art des Jahres.
    """
    row = db.execute(
        f"""
        SELECT
          COALESCE(SUM(CASE WHEN k.typ='einnahme' THEN p.betrag_cent ELSE 0 END), 0) AS einnahmen,
          COALESCE(SUM(CASE WHEN k.typ='ausgabe'  THEN {BETRIEBLICH_SQL} ELSE 0 END), 0) AS ausgaben,
          COALESCE(SUM(CASE WHEN k.key='einnahme_ku' THEN p.betrag_cent ELSE 0 END), 0) AS ku_umsatz,
          COALESCE(SUM(CASE WHEN k.key='einnahme_ust' THEN p.betrag_cent - p.ust_cent ELSE 0 END), 0) AS ust_umsatz_netto,
          COALESCE(SUM(CASE WHEN k.typ='einnahme' THEN p.ust_cent ELSE 0 END), 0) AS ust,
          COALESCE(SUM(CASE WHEN k.typ='ausgabe'  THEN {BETRIEBLICH_UST_SQL} ELSE 0 END), 0) AS vorsteuer
        FROM buchung_position p
        JOIN buchung b ON b.id = p.buchung_id
        JOIN kategorie k ON k.id = p.kategorie_id
        WHERE b.gewerbe_id = ? AND substr(b.datum,1,4) = ?
        """,
        (gewerbe_id, str(jahr)),
    ).fetchone()
    return {
        "einnahmen_cent": row["einnahmen"],
        "ausgaben_cent": row["ausgaben"],
        "ku_umsatz_cent": row["ku_umsatz"],
        # Gesamtumsatz i. S. d. §19 Abs. 2: KU-Einnahmen (brutto = Entgelt) + Regel-Einnahmen netto.
        "gesamtumsatz_cent": row["ku_umsatz"] + row["ust_umsatz_netto"],
        "ust_cent": row["ust"],
        "vorsteuer_cent": row["vorsteuer"],
        "besteuerung": best.art(db, gewerbe_id, jahr),
    }


def mit_ku_guard(werte: dict, vorjahr: dict | None = None) -> dict:
    """Ergänzt Grenzen und Warnungen nach §19 Abs. 1 UStG (Fassung ab 2025).

    - ku_warn_vorjahr: der Gesamtumsatz des VORJAHRES lag über 25.000 € → in diesem Jahr gilt die
      Kleinunternehmerregelung nicht (mehr). Braucht `vorjahr` (Ergebnis von `summen` für jahr - 1).
    - ku_warn_folgejahr: der Umsatz DIESES Jahres liegt über 25.000 € → im Folgejahr kein KU mehr.
    - ku_warn_laufend: der Umsatz dieses Jahres liegt über 100.000 € → KU entfällt sofort.
    Warnungen nur für Jahre, die in Tab als Kleinunternehmer laufen.
    """
    ist_ku = werte.get("besteuerung", best.KU) == best.KU
    ku = werte["ku_umsatz_cent"] if ist_ku else 0
    vj = (vorjahr or {}).get("gesamtumsatz_cent")
    return {
        **werte,
        "ku_grenze_vorjahr_cent": KU_GRENZE_VORJAHR_CENT,
        "ku_grenze_laufend_cent": KU_GRENZE_LAUFEND_CENT,
        "ku_umsatz_vorjahr_cent": vj,
        "ku_warn_vorjahr": bool(ist_ku and vj is not None and vj > KU_GRENZE_VORJAHR_CENT),
        "ku_warn_folgejahr": ku > KU_GRENZE_VORJAHR_CENT,
        "ku_warn_laufend": ku > KU_GRENZE_LAUFEND_CENT,
    }
