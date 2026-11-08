"""Meta-Endpunkte: verfügbare Mapping-Jahre + Kennzahlen inkl. KU-Grenz-Guard."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services import kennzahlen as kz

router = APIRouter(prefix="/api", tags=["meta"], dependencies=[Depends(get_current_user)])


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
    return {"gewerbe_id": gewerbe_id, "jahr": jahr, **kz.mit_ku_guard(kz.summen(db, gewerbe_id, jahr))}
