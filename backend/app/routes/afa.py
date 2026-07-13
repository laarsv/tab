"""AfA-Wirtschaftsgüter CRUD. Jahres-AfA wird berechnet (services/afa.py)."""
from __future__ import annotations

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import get_current_user
from ..db import get_db
from ..services.afa import jahres_afa_cent, restbuchwert_cent

router = APIRouter(prefix="/api/afa", tags=["afa"], dependencies=[Depends(get_current_user)])


def _valid_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("Datum muss im Format YYYY-MM-DD sein.")
    return value


class AfaIn(BaseModel):
    gewerbe_id: int
    kategorie_id: int
    bezeichnung: str = Field(min_length=1, max_length=160)
    anschaffungskosten_cent: int = Field(gt=0)
    anschaffungsdatum: str
    nutzungsdauer_jahre: int = Field(ge=1, le=50)
    abgang_datum: str | None = None
    beschreibung: str | None = None

    @field_validator("anschaffungsdatum")
    @classmethod
    def _v_date(cls, v: str) -> str:
        return _valid_date(v)

    @field_validator("abgang_datum")
    @classmethod
    def _v_abgang(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


class AfaPatch(BaseModel):
    kategorie_id: int | None = None
    bezeichnung: str | None = Field(default=None, min_length=1, max_length=160)
    anschaffungskosten_cent: int | None = Field(default=None, gt=0)
    anschaffungsdatum: str | None = None
    nutzungsdauer_jahre: int | None = Field(default=None, ge=1, le=50)
    abgang_datum: str | None = None  # explizit null = Abgang zurücknehmen
    beschreibung: str | None = None

    @field_validator("anschaffungsdatum", "abgang_datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


def _check_abgang(anschaffungsdatum: str, abgang_datum: str | None) -> None:
    if abgang_datum is not None and abgang_datum < anschaffungsdatum:
        raise HTTPException(400, "Abgangsdatum darf nicht vor dem Anschaffungsdatum liegen.")


def _afa_kategorie(db: sqlite3.Connection, kategorie_id: int) -> sqlite3.Row:
    k = db.execute("SELECT * FROM kategorie WHERE id = ?", (kategorie_id,)).fetchone()
    if k is None:
        raise HTTPException(404, "Kategorie nicht gefunden.")
    if not k["ist_afa"]:
        raise HTTPException(400, "Für AfA bitte eine AfA-Kategorie (ist_afa) wählen.")
    return k


@router.get("")
def list_afa(gewerbe_id: int, jahr: int | None = None, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        """
        SELECT a.*, k.name AS kategorie_name
        FROM afa_buchung a JOIN kategorie k ON k.id = a.kategorie_id
        WHERE a.gewerbe_id = ?
        ORDER BY a.anschaffungsdatum DESC, a.id DESC
        """,
        (gewerbe_id,),
    )
    out = []
    for r in rows:
        d = dict(r)
        if jahr is not None:
            d["jahres_afa_cent"] = jahres_afa_cent(
                r["anschaffungskosten_cent"],
                r["anschaffungsdatum"],
                r["nutzungsdauer_jahre"],
                jahr,
                r["abgang_datum"],
            )
        d["restbuchwert_cent"] = restbuchwert_cent(
            r["anschaffungskosten_cent"],
            r["anschaffungsdatum"],
            r["nutzungsdauer_jahre"],
            r["abgang_datum"],
        )
        out.append(d)
    return out


@router.post("", status_code=201)
def create_afa(body: AfaIn, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT 1 FROM gewerbe WHERE id = ?", (body.gewerbe_id,)).fetchone() is None:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    _afa_kategorie(db, body.kategorie_id)
    _check_abgang(body.anschaffungsdatum, body.abgang_datum)
    cur = db.execute(
        """
        INSERT INTO afa_buchung
            (gewerbe_id, kategorie_id, bezeichnung, anschaffungskosten_cent,
             anschaffungsdatum, nutzungsdauer_jahre, abgang_datum, beschreibung)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            body.gewerbe_id,
            body.kategorie_id,
            body.bezeichnung.strip(),
            body.anschaffungskosten_cent,
            body.anschaffungsdatum,
            body.nutzungsdauer_jahre,
            body.abgang_datum,
            (body.beschreibung or "").strip() or None,
        ),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM afa_buchung WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{afa_id}")
def update_afa(afa_id: int, body: AfaPatch, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM afa_buchung WHERE id = ?", (afa_id,)).fetchone()
    if cur is None:
        raise HTTPException(404, "AfA-Eintrag nicht gefunden.")
    if body.kategorie_id is not None:
        _afa_kategorie(db, body.kategorie_id)

    neues_anschaffung = body.anschaffungsdatum or cur["anschaffungsdatum"]
    if "abgang_datum" in body.model_fields_set:
        _check_abgang(neues_anschaffung, body.abgang_datum)
    elif body.anschaffungsdatum is not None:
        _check_abgang(neues_anschaffung, cur["abgang_datum"])

    fields, values = [], []
    for col, val in [
        ("kategorie_id", body.kategorie_id),
        ("bezeichnung", body.bezeichnung.strip() if body.bezeichnung else None),
        ("anschaffungskosten_cent", body.anschaffungskosten_cent),
        ("anschaffungsdatum", body.anschaffungsdatum),
        ("nutzungsdauer_jahre", body.nutzungsdauer_jahre),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val)
    if "abgang_datum" in body.model_fields_set:  # explizit null = Abgang zurücknehmen
        fields.append("abgang_datum = ?"); values.append(body.abgang_datum)
    if body.beschreibung is not None:
        fields.append("beschreibung = ?"); values.append(body.beschreibung.strip() or None)
    if fields:
        fields.append("updated_at = datetime('now')")
        db.execute(f"UPDATE afa_buchung SET {', '.join(fields)} WHERE id = ?", (*values, afa_id))
        db.commit()
    return dict(db.execute("SELECT * FROM afa_buchung WHERE id = ?", (afa_id,)).fetchone())


@router.delete("/{afa_id}", status_code=204)
def delete_afa(afa_id: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM afa_buchung WHERE id = ?", (afa_id,))
    db.commit()
