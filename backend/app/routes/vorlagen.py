"""Artikelkatalog und Textbausteine je Gewerbe (Aufbau nach Haben, schlank).

Artikel = häufige Positionen (Bezeichnung + Preis, Kleinunternehmer: brutto = netto), Textbausteine =
wiederverwendbare Texte für Notiz bzw. Einleitung von Rechnungen und Angeboten. Beides ist reine Bequemlichkeit:
Rechnungen und Angebote speichern immer ihre eigenen Werte, ändern oder löschen hier berührt sie nicht.
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db

router = APIRouter(prefix="/api", tags=["vorlagen"], dependencies=[Depends(get_current_user)])


# ── Artikel ─────────────────────────────────────────────────────────────────

class ArtikelIn(BaseModel):
    gewerbe_id: int
    bezeichnung: str = Field(min_length=1, max_length=500)
    preis_cent: int = Field(gt=0, le=100_000_000_00)


class ArtikelPatch(BaseModel):
    bezeichnung: str | None = Field(default=None, min_length=1, max_length=500)
    preis_cent: int | None = Field(default=None, gt=0, le=100_000_000_00)


def _artikel(db: sqlite3.Connection, user: dict, artikel_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM artikel WHERE id = ?", (artikel_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Artikel nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    return row


@router.get("/artikel")
def artikel_liste(gewerbe_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, gewerbe_id)
    return [
        dict(r)
        for r in db.execute(
            "SELECT * FROM artikel WHERE gewerbe_id = ? ORDER BY bezeichnung COLLATE NOCASE", (gewerbe_id,)
        )
    ]


@router.post("/artikel", status_code=201)
def artikel_anlegen(
    body: ArtikelIn,
    response: Response,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Legt an — oder aktualisiert den Preis, wenn es die Bezeichnung schon gibt (200 statt 201).
    So taugt dieselbe Route für „Position als Artikel speichern“."""
    check_gewerbe(db, user, body.gewerbe_id)
    name = body.bezeichnung.strip()
    vorhanden = db.execute(
        "SELECT id FROM artikel WHERE gewerbe_id = ? AND bezeichnung = ?", (body.gewerbe_id, name)
    ).fetchone()
    if vorhanden:
        db.execute(
            "UPDATE artikel SET preis_cent = ?, updated_at = datetime('now') WHERE id = ?",
            (body.preis_cent, vorhanden["id"]),
        )
        response.status_code = 200
        aid = vorhanden["id"]
    else:
        aid = db.execute(
            "INSERT INTO artikel (gewerbe_id, bezeichnung, preis_cent) VALUES (?, ?, ?)",
            (body.gewerbe_id, name, body.preis_cent),
        ).lastrowid
    db.commit()
    return dict(db.execute("SELECT * FROM artikel WHERE id = ?", (aid,)).fetchone())


@router.patch("/artikel/{artikel_id}")
def artikel_aendern(
    artikel_id: int,
    body: ArtikelPatch,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _artikel(db, user, artikel_id)
    fields, values = [], []
    if body.bezeichnung is not None:
        fields.append("bezeichnung = ?"); values.append(body.bezeichnung.strip())
    if body.preis_cent is not None:
        fields.append("preis_cent = ?"); values.append(body.preis_cent)
    if fields:
        fields.append("updated_at = datetime('now')")
        try:
            db.execute(f"UPDATE artikel SET {', '.join(fields)} WHERE id = ?", (*values, artikel_id))
        except sqlite3.IntegrityError:
            raise HTTPException(400, "Einen Artikel mit dieser Bezeichnung gibt es schon.")
        db.commit()
    return dict(db.execute("SELECT * FROM artikel WHERE id = ?", (artikel_id,)).fetchone())


@router.delete("/artikel/{artikel_id}", status_code=204)
def artikel_loeschen(artikel_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _artikel(db, user, artikel_id)
    db.execute("DELETE FROM artikel WHERE id = ?", (artikel_id,))
    db.commit()


# ── Textbausteine ───────────────────────────────────────────────────────────

class BausteinIn(BaseModel):
    gewerbe_id: int
    name: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=2000)


class BausteinPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    text: str | None = Field(default=None, min_length=1, max_length=2000)


def _baustein(db: sqlite3.Connection, user: dict, baustein_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM textbaustein WHERE id = ?", (baustein_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Textbaustein nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    return row


@router.get("/textbausteine")
def bausteine_liste(gewerbe_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, gewerbe_id)
    return [
        dict(r)
        for r in db.execute("SELECT * FROM textbaustein WHERE gewerbe_id = ? ORDER BY name COLLATE NOCASE", (gewerbe_id,))
    ]


@router.post("/textbausteine", status_code=201)
def baustein_anlegen(body: BausteinIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    try:
        bid = db.execute(
            "INSERT INTO textbaustein (gewerbe_id, name, text) VALUES (?, ?, ?)",
            (body.gewerbe_id, body.name.strip(), body.text.strip()),
        ).lastrowid
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Einen Textbaustein mit diesem Namen gibt es schon.")
    db.commit()
    return dict(db.execute("SELECT * FROM textbaustein WHERE id = ?", (bid,)).fetchone())


@router.patch("/textbausteine/{baustein_id}")
def baustein_aendern(
    baustein_id: int,
    body: BausteinPatch,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _baustein(db, user, baustein_id)
    fields, values = [], []
    if body.name is not None:
        fields.append("name = ?"); values.append(body.name.strip())
    if body.text is not None:
        fields.append("text = ?"); values.append(body.text.strip())
    if fields:
        fields.append("updated_at = datetime('now')")
        try:
            db.execute(f"UPDATE textbaustein SET {', '.join(fields)} WHERE id = ?", (*values, baustein_id))
        except sqlite3.IntegrityError:
            raise HTTPException(400, "Einen Textbaustein mit diesem Namen gibt es schon.")
        db.commit()
    return dict(db.execute("SELECT * FROM textbaustein WHERE id = ?", (baustein_id,)).fetchone())


@router.delete("/textbausteine/{baustein_id}", status_code=204)
def baustein_loeschen(baustein_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _baustein(db, user, baustein_id)
    db.execute("DELETE FROM textbaustein WHERE id = ?", (baustein_id,))
    db.commit()
