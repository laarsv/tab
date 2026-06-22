"""EÜR-Export: Summenblatt (JSON + CSV) und Beleg-Journal (CSV) pro Gewerbe + Jahr."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from ..auth.deps import get_current_user
from ..db import get_db
from ..services.export import (
    BesteuerungNotSupportedError,
    MappingMissingError,
    build_summenblatt,
    journal_csv,
    summenblatt_csv,
)

router = APIRouter(prefix="/api/export", tags=["export"], dependencies=[Depends(get_current_user)])


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in name).strip("-").lower() or "gewerbe"


@router.get("/summenblatt")
def summenblatt(gewerbe_id: int, jahr: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        return build_summenblatt(db, gewerbe_id, jahr)
    except (MappingMissingError, BesteuerungNotSupportedError) as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/summenblatt.csv")
def summenblatt_download(gewerbe_id: int, jahr: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        data = summenblatt_csv(db, gewerbe_id, jahr)
    except (MappingMissingError, BesteuerungNotSupportedError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    g = db.execute("SELECT name FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    name = _slug(g["name"]) if g else "gewerbe"
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="euer-summenblatt-{name}-{jahr}.csv"'},
    )


@router.get("/journal.csv")
def journal_download(gewerbe_id: int, jahr: int, db: sqlite3.Connection = Depends(get_db)):
    try:
        data = journal_csv(db, gewerbe_id, jahr)
    except (MappingMissingError, BesteuerungNotSupportedError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    g = db.execute("SELECT name FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    name = _slug(g["name"]) if g else "gewerbe"
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="beleg-journal-{name}-{jahr}.csv"'},
    )
