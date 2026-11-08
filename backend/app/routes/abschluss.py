"""Jahresabschluss: Jahr abschließen/öffnen, prüfen, Änderungsprotokoll.

Sperre und Protokoll selbst stecken als Trigger in der Datenbank (services/audit.py); diese Routen
bedienen nur den Abschluss und zeigen das Protokoll. Alles hängt am Gewerbe (check_gewerbe).
"""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services import abschluss as svc
from ..services.audit import kopf
from ..services.export import protokoll_csv

router = APIRouter(prefix="/api/abschluss", tags=["abschluss"])


def _eintrag(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "ts": r["ts"],
        "actor": r["actor"],
        "tabelle": r["tabelle"],
        "zeile_id": r["zeile_id"],
        "aktion": r["aktion"],
        "vorher": r["vorher"],
        "nachher": r["nachher"],
        "hash": r["row_hash"],
    }


@router.get("")
def uebersicht(
    gewerbe_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    return {"jahre": svc.jahre(db, gewerbe_id), "kopf": kopf(db)}


@router.get("/status")
def status(
    gewerbe_id: int,
    jahr: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Leichtgewichtig für Seitenleiste und Hinweisbänder: ist das Jahr abgeschlossen?"""
    check_gewerbe(db, user, gewerbe_id)
    return {"abgeschlossen": svc.ist_abgeschlossen(db, gewerbe_id, jahr)}


class JahrIn(BaseModel):
    gewerbe_id: int
    jahr: int = Field(ge=2000, le=2100)


@router.post("/schliessen")
def schliessen(
    body: JahrIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, body.gewerbe_id)
    try:
        return svc.schliessen(db, body.gewerbe_id, body.jahr, user["email"])
    except svc.AbschlussError as e:
        raise HTTPException(400, str(e))


class OeffnenIn(JahrIn):
    begruendung: str = Field(min_length=1, max_length=500)


@router.post("/oeffnen")
def oeffnen(
    body: OeffnenIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, body.gewerbe_id)
    try:
        svc.oeffnen(db, body.gewerbe_id, body.jahr, user["email"], body.begruendung)
    except svc.AbschlussError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


class PruefenIn(BaseModel):
    gewerbe_id: int


@router.post("/pruefen")
def pruefen(
    body: PruefenIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, body.gewerbe_id)
    return svc.pruefen(db, body.gewerbe_id)


@router.get("/protokoll")
def protokoll(
    gewerbe_id: int,
    limit: int = 50,
    vor_id: int | None = None,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Änderungsprotokoll des Gewerbes, neueste zuerst; mit `vor_id` blättert man weiter zurück."""
    check_gewerbe(db, user, gewerbe_id)
    limit = max(1, min(limit, 200))
    sql = "SELECT * FROM audit_log WHERE gewerbe_id = ?"
    args: list = [gewerbe_id]
    if vor_id is not None:
        sql += " AND id < ?"
        args.append(vor_id)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(limit + 1)
    rows = db.execute(sql, args).fetchall()
    return {"eintraege": [_eintrag(r) for r in rows[:limit]], "weitere": len(rows) > limit}


@router.get("/protokoll.csv")
def protokoll_download(
    gewerbe_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    return Response(
        content=protokoll_csv(db, gewerbe_id),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="aenderungsprotokoll.csv"'},
    )
