"""Gewerbe-Verwaltung: anlegen, umbenennen, (de)aktivieren. Kein Löschen."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import get_current_user
from ..db import get_db

router = APIRouter(prefix="/api/gewerbe", tags=["gewerbe"], dependencies=[Depends(get_current_user)])


BESTEUERUNG = {"kleinunternehmer", "regelbesteuerung"}


class GewerbeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    steuernummer: str | None = None
    besteuerung: str = "kleinunternehmer"
    anschrift: str | None = None          # Rechnungs-Absender (Name + Adresse, mehrzeilig)
    iban: str | None = None
    rechnung_fusszeile: str | None = None

    @field_validator("besteuerung")
    @classmethod
    def _v_best(cls, v: str) -> str:
        if v not in BESTEUERUNG:
            raise ValueError("besteuerung muss 'kleinunternehmer' oder 'regelbesteuerung' sein.")
        return v


class GewerbePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    steuernummer: str | None = None
    aktiv: bool | None = None
    besteuerung: str | None = None
    anschrift: str | None = None
    iban: str | None = None
    rechnung_fusszeile: str | None = None

    @field_validator("besteuerung")
    @classmethod
    def _v_best(cls, v: str | None) -> str | None:
        if v is not None and v not in BESTEUERUNG:
            raise ValueError("besteuerung muss 'kleinunternehmer' oder 'regelbesteuerung' sein.")
        return v


@router.get("")
def list_gewerbe(include_inactive: bool = False, db: sqlite3.Connection = Depends(get_db)):
    sql = "SELECT * FROM gewerbe"
    if not include_inactive:
        sql += " WHERE aktiv = 1"
    sql += " ORDER BY aktiv DESC, name COLLATE NOCASE"
    return [dict(r) for r in db.execute(sql)]


@router.post("", status_code=201)
def create_gewerbe(body: GewerbeIn, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        "INSERT INTO gewerbe (name, steuernummer, besteuerung, anschrift, iban, rechnung_fusszeile) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            body.name.strip(),
            (body.steuernummer or "").strip() or None,
            body.besteuerung,
            (body.anschrift or "").strip() or None,
            (body.iban or "").strip() or None,
            (body.rechnung_fusszeile or "").strip() or None,
        ),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM gewerbe WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{gewerbe_id}")
def update_gewerbe(gewerbe_id: int, body: GewerbePatch, db: sqlite3.Connection = Depends(get_db)):
    row = db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    fields, values = [], []
    if body.name is not None:
        fields.append("name = ?"); values.append(body.name.strip())
    if body.steuernummer is not None:
        fields.append("steuernummer = ?"); values.append(body.steuernummer.strip() or None)
    if body.aktiv is not None:
        fields.append("aktiv = ?"); values.append(1 if body.aktiv else 0)
    if body.besteuerung is not None:
        fields.append("besteuerung = ?"); values.append(body.besteuerung)
    for col, val in [
        ("anschrift", body.anschrift),
        ("iban", body.iban),
        ("rechnung_fusszeile", body.rechnung_fusszeile),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val.strip() or None)
    if fields:
        fields.append("updated_at = datetime('now')")
        db.execute(f"UPDATE gewerbe SET {', '.join(fields)} WHERE id = ?", (*values, gewerbe_id))
        db.commit()
    return dict(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone())
