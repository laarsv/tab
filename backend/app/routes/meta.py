"""Meta-Endpunkte: verfügbare Mapping-Jahre + Kennzahlen inkl. KU-Grenz-Guard."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db

router = APIRouter(prefix="/api", tags=["meta"], dependencies=[Depends(get_current_user)])

# §19 UStG Kleinunternehmer-Grenzen (brutto), in Cent.
KU_GRENZE_VORJAHR_CENT = 25_000_00
KU_GRENZE_LAUFEND_CENT = 100_000_00


@router.get("/meta/jahre")
def list_jahre(db: sqlite3.Connection = Depends(get_db)):
    return [dict(r) for r in db.execute("SELECT * FROM euer_jahr ORDER BY jahr DESC")]


@router.get("/kennzahlen")
def kennzahlen(
    gewerbe_id: int,
    jahr: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    # ku_umsatz: Gesamtumsatz i. S. d. §19 Abs. 2 UStG — steuerfreie Umsätze nach
    # §4 Nr. 11 (Courtage) und Verkäufe von Anlagevermögen bleiben außer Ansatz.
    row = db.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN k.typ='einnahme' THEN p.betrag_cent ELSE 0 END), 0) AS einnahmen,
          COALESCE(SUM(CASE WHEN k.typ='ausgabe'  THEN p.betrag_cent ELSE 0 END), 0) AS ausgaben,
          COALESCE(SUM(CASE WHEN k.key='einnahme_ku' THEN p.betrag_cent ELSE 0 END), 0) AS ku_umsatz
        FROM buchung_position p
        JOIN buchung b ON b.id = p.buchung_id
        JOIN kategorie k ON k.id = p.kategorie_id
        WHERE b.gewerbe_id = ? AND substr(b.datum,1,4) = ?
        """,
        (gewerbe_id, str(jahr)),
    ).fetchone()
    ku_umsatz = row["ku_umsatz"]
    return {
        "gewerbe_id": gewerbe_id,
        "jahr": jahr,
        "einnahmen_cent": row["einnahmen"],
        "ausgaben_cent": row["ausgaben"],
        "ku_umsatz_cent": ku_umsatz,
        "ku_grenze_vorjahr_cent": KU_GRENZE_VORJAHR_CENT,
        "ku_grenze_laufend_cent": KU_GRENZE_LAUFEND_CENT,
        "ku_warn_vorjahr": ku_umsatz > KU_GRENZE_VORJAHR_CENT,
        "ku_warn_laufend": ku_umsatz > KU_GRENZE_LAUFEND_CENT,
    }
