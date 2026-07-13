"""Fahrten-Liste (km-Pauschale, Privatwagen). Nachweis-Liste, kein Fahrtenbuch:
Datum, Ziel, Anlass, km. Summe × 0,30 €/km wird als normale Buchung
(Kategorie fahrtkosten_kfz) übernommen — hier wird nichts exportiert."""
from __future__ import annotations

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import get_current_user
from ..db import get_db

router = APIRouter(prefix="/api/fahrten", tags=["fahrten"], dependencies=[Depends(get_current_user)])

KM_SATZ_CENT = 30  # 0,30 €/km


def _valid_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("datum muss im Format YYYY-MM-DD sein.")
    return value


class FahrtIn(BaseModel):
    gewerbe_id: int
    datum: str
    ziel: str = Field(min_length=1, max_length=200)
    anlass: str | None = Field(default=None, max_length=200)
    km: float = Field(gt=0, le=100000)

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str) -> str:
        return _valid_date(v)


class FahrtPatch(BaseModel):
    datum: str | None = None
    ziel: str | None = Field(default=None, min_length=1, max_length=200)
    anlass: str | None = Field(default=None, max_length=200)
    km: float | None = Field(default=None, gt=0, le=100000)

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


@router.get("")
def list_fahrten(gewerbe_id: int, jahr: int, db: sqlite3.Connection = Depends(get_db)):
    rows = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM fahrt WHERE gewerbe_id = ? AND substr(datum,1,4) = ? "
            "ORDER BY datum DESC, id DESC",
            (gewerbe_id, str(jahr)),
        )
    ]
    summe_km = sum(r["km"] for r in rows)
    return {
        "fahrten": rows,
        "summe_km": round(summe_km, 1),
        "betrag_cent": round(summe_km * KM_SATZ_CENT),
        "km_satz_cent": KM_SATZ_CENT,
    }


@router.post("", status_code=201)
def create_fahrt(body: FahrtIn, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT 1 FROM gewerbe WHERE id = ?", (body.gewerbe_id,)).fetchone() is None:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    cur = db.execute(
        "INSERT INTO fahrt (gewerbe_id, datum, ziel, anlass, km) VALUES (?, ?, ?, ?, ?)",
        (
            body.gewerbe_id,
            body.datum,
            body.ziel.strip(),
            (body.anlass or "").strip() or None,
            body.km,
        ),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM fahrt WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{fahrt_id}")
def update_fahrt(fahrt_id: int, body: FahrtPatch, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT 1 FROM fahrt WHERE id = ?", (fahrt_id,)).fetchone() is None:
        raise HTTPException(404, "Fahrt nicht gefunden.")
    fields, values = [], []
    if body.datum is not None:
        fields.append("datum = ?"); values.append(body.datum)
    if body.ziel is not None:
        fields.append("ziel = ?"); values.append(body.ziel.strip())
    if body.anlass is not None:
        fields.append("anlass = ?"); values.append(body.anlass.strip() or None)
    if body.km is not None:
        fields.append("km = ?"); values.append(body.km)
    if fields:
        db.execute(f"UPDATE fahrt SET {', '.join(fields)} WHERE id = ?", (*values, fahrt_id))
        db.commit()
    return dict(db.execute("SELECT * FROM fahrt WHERE id = ?", (fahrt_id,)).fetchone())


@router.delete("/{fahrt_id}", status_code=204)
def delete_fahrt(fahrt_id: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM fahrt WHERE id = ?", (fahrt_id,))
    db.commit()
