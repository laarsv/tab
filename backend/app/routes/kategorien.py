"""Kategorien für Dropdowns. Optional mit aufgelöster EÜR-Zeile für ein Jahr."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ..auth.deps import get_current_user
from ..db import get_db

router = APIRouter(
    prefix="/api/kategorien", tags=["kategorien"], dependencies=[Depends(get_current_user)]
)


@router.get("")
def list_kategorien(jahr: int | None = None, db: sqlite3.Connection = Depends(get_db)):
    if jahr is None:
        rows = db.execute("SELECT * FROM kategorie WHERE aktiv = 1 ORDER BY sort_order, id")
        return [dict(r) for r in rows]
    rows = db.execute(
        """
        SELECT k.*, m.zeile_nummer AS euer_zeile
        FROM kategorie k
        LEFT JOIN euer_mapping m ON m.kategorie_id = k.id AND m.jahr = ?
        WHERE k.aktiv = 1
        ORDER BY k.sort_order, k.id
        """,
        (jahr,),
    )
    return [dict(r) for r in rows]
