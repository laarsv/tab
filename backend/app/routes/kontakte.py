"""Kontakte (Rechnungsempfänger) je Gewerbe. Füllen sich automatisch: beim
Erstellen von Rechnungen/Abos wird der Empfänger upsertet (Name eindeutig je
Gewerbe, case-insensitiv). CRUD hier ist nur für Pflege/Korrekturen."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db

router = APIRouter(prefix="/api/kontakte", tags=["kontakte"], dependencies=[Depends(get_current_user)])


def upsert_kontakt(
    db: sqlite3.Connection,
    gewerbe_id: int,
    name: str,
    anschrift: str | None = None,
    email: str | None = None,
) -> None:
    """Kontakt anlegen oder Felder aktualisieren (nur nicht-leere Werte überschreiben)."""
    name = (name or "").strip()
    if not name:
        return
    row = db.execute(
        "SELECT id FROM kontakt WHERE gewerbe_id = ? AND name = ?", (gewerbe_id, name)
    ).fetchone()
    if row is None:
        db.execute(
            "INSERT INTO kontakt (gewerbe_id, name, anschrift, email) VALUES (?, ?, ?, ?)",
            (gewerbe_id, name, (anschrift or "").strip() or None, (email or "").strip() or None),
        )
        return
    sets, vals = [], []
    if (anschrift or "").strip():
        sets.append("anschrift = ?"); vals.append(anschrift.strip())
    if (email or "").strip():
        sets.append("email = ?"); vals.append(email.strip())
    if sets:
        sets.append("updated_at = datetime('now')")
        db.execute(f"UPDATE kontakt SET {', '.join(sets)} WHERE id = ?", (*vals, row["id"]))


class KontaktIn(BaseModel):
    gewerbe_id: int
    name: str = Field(min_length=1, max_length=200)
    anschrift: str | None = None
    email: str | None = None
    notiz: str | None = None


class KontaktPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    anschrift: str | None = None
    email: str | None = None
    notiz: str | None = None


@router.get("")
def list_kontakte(
    gewerbe_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    return [
        dict(r)
        for r in db.execute(
            "SELECT * FROM kontakt WHERE gewerbe_id = ? ORDER BY name COLLATE NOCASE",
            (gewerbe_id,),
        )
    ]


@router.post("", status_code=201)
def create_kontakt(
    body: KontaktIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, body.gewerbe_id)
    if db.execute(
        "SELECT 1 FROM kontakt WHERE gewerbe_id = ? AND name = ?",
        (body.gewerbe_id, body.name.strip()),
    ).fetchone():
        raise HTTPException(400, "Kontakt mit diesem Namen existiert bereits.")
    cur = db.execute(
        "INSERT INTO kontakt (gewerbe_id, name, anschrift, email, notiz) VALUES (?, ?, ?, ?, ?)",
        (
            body.gewerbe_id,
            body.name.strip(),
            (body.anschrift or "").strip() or None,
            (body.email or "").strip() or None,
            (body.notiz or "").strip() or None,
        ),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM kontakt WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{kontakt_id}")
def update_kontakt(
    kontakt_id: int,
    body: KontaktPatch,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM kontakt WHERE id = ?", (kontakt_id,)).fetchone()
    if cur is None:
        raise HTTPException(404, "Kontakt nicht gefunden.")
    check_gewerbe(db, user, cur["gewerbe_id"])
    fields, values = [], []
    if body.name is not None:
        fields.append("name = ?"); values.append(body.name.strip())
    for col, val in [("anschrift", body.anschrift), ("email", body.email), ("notiz", body.notiz)]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val.strip() or None)
    if fields:
        fields.append("updated_at = datetime('now')")
        try:
            db.execute(f"UPDATE kontakt SET {', '.join(fields)} WHERE id = ?", (*values, kontakt_id))
        except sqlite3.IntegrityError:
            raise HTTPException(400, "Kontakt mit diesem Namen existiert bereits.")
        db.commit()
    return dict(db.execute("SELECT * FROM kontakt WHERE id = ?", (kontakt_id,)).fetchone())


@router.delete("/{kontakt_id}", status_code=204)
def delete_kontakt(
    kontakt_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM kontakt WHERE id = ?", (kontakt_id,)).fetchone()
    if cur is not None:
        check_gewerbe(db, user, cur["gewerbe_id"])
    db.execute("DELETE FROM kontakt WHERE id = ?", (kontakt_id,))
    db.commit()
