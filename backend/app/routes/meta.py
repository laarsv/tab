"""Meta-Endpunkte: verfügbare Mapping-Jahre + Kennzahlen inkl. KU-Grenz-Guard."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ..auth.deps import get_current_user
from ..db import get_db

router = APIRouter(prefix="/api", tags=["meta"], dependencies=[Depends(get_current_user)])

# §19 UStG Kleinunternehmer-Grenzen (brutto), in Cent.
KU_GRENZE_VORJAHR_CENT = 25_000_00
KU_GRENZE_LAUFEND_CENT = 100_000_00


@router.get("/meta/jahre")
def list_jahre(db: sqlite3.Connection = Depends(get_db)):
    return [dict(r) for r in db.execute("SELECT * FROM euer_jahr ORDER BY jahr DESC")]


@router.get("/kennzahlen")
def kennzahlen(gewerbe_id: int, jahr: int, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN k.typ='einnahme' THEN b.betrag_cent ELSE 0 END), 0) AS einnahmen,
          COALESCE(SUM(CASE WHEN k.typ='ausgabe'  THEN b.betrag_cent ELSE 0 END), 0) AS ausgaben
        FROM buchung b JOIN kategorie k ON k.id = b.kategorie_id
        WHERE b.gewerbe_id = ? AND substr(b.datum,1,4) = ?
        """,
        (gewerbe_id, str(jahr)),
    ).fetchone()
    einnahmen = row["einnahmen"]
    return {
        "gewerbe_id": gewerbe_id,
        "jahr": jahr,
        "einnahmen_cent": einnahmen,
        "ausgaben_cent": row["ausgaben"],
        "ku_grenze_vorjahr_cent": KU_GRENZE_VORJAHR_CENT,
        "ku_grenze_laufend_cent": KU_GRENZE_LAUFEND_CENT,
        "ku_warn_vorjahr": einnahmen > KU_GRENZE_VORJAHR_CENT,
        "ku_warn_laufend": einnahmen > KU_GRENZE_LAUFEND_CENT,
    }
