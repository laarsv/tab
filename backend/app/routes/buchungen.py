"""Buchungen CRUD (normale Einnahmen/Ausgaben). AfA läuft über /api/afa."""
from __future__ import annotations

import datetime as dt
import os
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import get_current_user
from ..config import settings
from ..db import get_db

router = APIRouter(
    prefix="/api/buchungen", tags=["buchungen"], dependencies=[Depends(get_current_user)]
)


def _valid_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("datum muss im Format YYYY-MM-DD sein.")
    return value


class BuchungIn(BaseModel):
    gewerbe_id: int
    datum: str
    betrag_cent: int = Field(gt=0)
    kategorie_id: int
    beschreibung: str | None = None
    beleg_details: str | None = None

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str) -> str:
        return _valid_date(v)


class BuchungPatch(BaseModel):
    datum: str | None = None
    betrag_cent: int | None = Field(default=None, gt=0)
    kategorie_id: int | None = None
    beschreibung: str | None = None
    beleg_details: str | None = None

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


def _kategorie(db: sqlite3.Connection, kategorie_id: int) -> sqlite3.Row:
    k = db.execute("SELECT * FROM kategorie WHERE id = ?", (kategorie_id,)).fetchone()
    if k is None:
        raise HTTPException(404, "Kategorie nicht gefunden.")
    if k["ist_afa"]:
        raise HTTPException(400, "AfA-Kategorien bitte über die AfA-Erfassung anlegen.")
    return k


def _check_beleg(k: sqlite3.Row, beleg_details: str | None) -> None:
    if k["belegpflicht_extra"] and not (beleg_details and beleg_details.strip()):
        raise HTTPException(400, f"Für „{k['name']}“ sind Beleg-Details Pflicht.")


def _row(db: sqlite3.Connection, buchung_id: int) -> dict:
    r = db.execute(
        """
        SELECT b.*, k.name AS kategorie_name, k.typ AS kategorie_typ,
               k.belegpflicht_extra, k.abzug_quote,
               (SELECT COUNT(*) FROM beleg WHERE beleg.buchung_id = b.id) AS beleg_count
        FROM buchung b JOIN kategorie k ON k.id = b.kategorie_id
        WHERE b.id = ?
        """,
        (buchung_id,),
    ).fetchone()
    return dict(r)


@router.get("")
def list_buchungen(
    gewerbe_id: int, jahr: int | None = None, db: sqlite3.Connection = Depends(get_db)
):
    sql = (
        "SELECT b.*, k.name AS kategorie_name, k.typ AS kategorie_typ, "
        "k.belegpflicht_extra, k.abzug_quote, "
        "(SELECT COUNT(*) FROM beleg WHERE beleg.buchung_id = b.id) AS beleg_count "
        "FROM buchung b JOIN kategorie k ON k.id = b.kategorie_id "
        "WHERE b.gewerbe_id = ?"
    )
    params: list = [gewerbe_id]
    if jahr is not None:
        sql += " AND substr(b.datum,1,4) = ?"
        params.append(str(jahr))
    sql += " ORDER BY b.datum DESC, b.id DESC"
    return [dict(r) for r in db.execute(sql, params)]


@router.post("", status_code=201)
def create_buchung(body: BuchungIn, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT 1 FROM gewerbe WHERE id = ?", (body.gewerbe_id,)).fetchone() is None:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    k = _kategorie(db, body.kategorie_id)
    _check_beleg(k, body.beleg_details)
    cur = db.execute(
        """
        INSERT INTO buchung (gewerbe_id, datum, betrag_cent, kategorie_id, beschreibung, beleg_details)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            body.gewerbe_id,
            body.datum,
            body.betrag_cent,
            body.kategorie_id,
            (body.beschreibung or "").strip() or None,
            (body.beleg_details or "").strip() or None,
        ),
    )
    db.commit()
    return _row(db, cur.lastrowid)


@router.patch("/{buchung_id}")
def update_buchung(buchung_id: int, body: BuchungPatch, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM buchung WHERE id = ?", (buchung_id,)).fetchone()
    if cur is None:
        raise HTTPException(404, "Buchung nicht gefunden.")

    kategorie_id = body.kategorie_id if body.kategorie_id is not None else cur["kategorie_id"]
    k = _kategorie(db, kategorie_id)
    beleg = body.beleg_details if body.beleg_details is not None else cur["beleg_details"]
    _check_beleg(k, beleg)

    fields, values = [], []
    if body.datum is not None:
        fields.append("datum = ?"); values.append(body.datum)
    if body.betrag_cent is not None:
        fields.append("betrag_cent = ?"); values.append(body.betrag_cent)
    if body.kategorie_id is not None:
        fields.append("kategorie_id = ?"); values.append(body.kategorie_id)
    if body.beschreibung is not None:
        fields.append("beschreibung = ?"); values.append(body.beschreibung.strip() or None)
    if body.beleg_details is not None:
        fields.append("beleg_details = ?"); values.append(body.beleg_details.strip() or None)
    if fields:
        fields.append("updated_at = datetime('now')")
        db.execute(f"UPDATE buchung SET {', '.join(fields)} WHERE id = ?", (*values, buchung_id))
        db.commit()
    return _row(db, buchung_id)


@router.delete("/{buchung_id}", status_code=204)
def delete_buchung(buchung_id: int, db: sqlite3.Connection = Depends(get_db)):
    # Beleg-Dateien auf der Platte miträumen (DB-Rows gehen per ON DELETE CASCADE).
    for r in db.execute("SELECT stored_name FROM beleg WHERE buchung_id = ?", (buchung_id,)):
        path = os.path.join(settings.UPLOAD_ROOT, r["stored_name"])
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
    db.execute("DELETE FROM buchung WHERE id = ?", (buchung_id,))
    db.commit()
