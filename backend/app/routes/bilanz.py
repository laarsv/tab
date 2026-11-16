"""Bilanz und GuV (Entwurf für die Steuerberatung, BILANZ.md). Rechnet in services/bilanz.py; hier nur Lesen,
Eröffnungswerte und Abschlussbuchungen. Jahres-Sperre über die Trigger (services/audit.py)."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services import bilanz as bz
from ..services import gewinnermittlung as gw

router = APIRouter(prefix="/api/bilanz", tags=["bilanz"])


def _nur_bilanz(db: sqlite3.Connection, gewerbe_id: int, jahr: int) -> None:
    if not gw.ist_bilanz(db, gewerbe_id, jahr):
        raise HTTPException(400, f"{jahr} ist für dieses Gewerbe kein Bilanz-Jahr. Gewinnermittlung im Gewerbe-Dialog umstellen.")


def _konten(db: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    out = [{"konto": f"bank:{k['id']}", "name": f"Bank {k['name']}"}
           for k in db.execute("SELECT id, name FROM bankkonto WHERE gewerbe_id = ? ORDER BY id", (gewerbe_id,))]
    out += [{"konto": k, "name": bz.KONTO_NAMEN[k]} for k in bz.ABSCHLUSS_KONTEN]
    out += [{"konto": f"guv:{p[0]}", "name": f"GuV {p[1]} {p[2]}"} for p in bz.GUV_POSTEN]
    return out


@router.get("")
def bilanz_lesen(gewerbe_id: int, jahr: int, user: dict = Depends(get_current_user),
                 db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, gewerbe_id)
    _nur_bilanz(db, gewerbe_id, jahr)
    out = bz.auswertung(db, gewerbe_id, jahr)
    erstes = out["erstes_bilanzjahr"]
    out["eroeffnung"] = {
        "manuell": erstes == jahr,
        "werte": [dict(r) for r in db.execute(
            "SELECT posten, betrag_cent, text FROM bilanz_eroeffnung WHERE gewerbe_id = ? AND jahr = ? ORDER BY posten",
            (gewerbe_id, jahr))],
        "salden": [{"konto": k, "name": bz.konto_name(db, k), "saldo_cent": v}
                   for k, v in sorted(bz.eroeffnung(db, gewerbe_id, jahr).items()) if v],
        "vorschlag": bz.eroeffnung_vorschlag(db, gewerbe_id, jahr) if erstes == jahr else None,
        "posten_aktiv": [{"posten": f"bank:{k['id']}", "name": f"Bank {k['name']}"}
                         for k in db.execute("SELECT id, name FROM bankkonto WHERE gewerbe_id = ? ORDER BY id", (gewerbe_id,))]
                        + [{"posten": p, "name": bz.KONTO_NAMEN[p]} for p in bz.EROEFFNUNG_AKTIV],
        "posten_passiv": [{"posten": p, "name": bz.KONTO_NAMEN[p]} for p in bz.EROEFFNUNG_PASSIV],
    }
    out["abschlussbuchungen"] = [
        {**dict(r), "soll_name": bz.konto_name(db, r["soll"]), "haben_name": bz.konto_name(db, r["haben"])}
        for r in db.execute(
            "SELECT id, datum, soll, haben, betrag_cent, text FROM abschlussbuchung WHERE gewerbe_id = ? "
            "AND datum BETWEEN ? AND ? ORDER BY datum, id", (gewerbe_id, f"{jahr}-01-01", f"{jahr}-12-31"))
    ]
    out["konten"] = _konten(db, gewerbe_id)
    return out


@router.get("/journal")
def journal_lesen(gewerbe_id: int, jahr: int, user: dict = Depends(get_current_user),
                  db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, gewerbe_id)
    _nur_bilanz(db, gewerbe_id, jahr)
    namen: dict[str, str] = {}

    def n(k):
        if k not in namen:
            namen[k] = bz.konto_name(db, k)
        return namen[k]
    return [{**z, "soll_name": n(z["soll"]), "haben_name": n(z["haben"])} for z in bz.journal(db, gewerbe_id, jahr)]


@router.get("/bilanz.csv")
def bilanz_csv(gewerbe_id: int, jahr: int, user: dict = Depends(get_current_user),
               db: sqlite3.Connection = Depends(get_db)):
    g = check_gewerbe(db, user, gewerbe_id)
    _nur_bilanz(db, gewerbe_id, jahr)
    return Response(bz.csv_text(db, gewerbe_id, jahr, g["name"]).encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="bilanz-{jahr}.csv"'})



# ── Eröffnung ────────────────────────────────────────────────────────────────

class EroeffnungWert(BaseModel):
    posten: str
    betrag_cent: int = Field(ge=0)
    text: str | None = Field(default=None, max_length=200)


class EroeffnungIn(BaseModel):
    gewerbe_id: int
    jahr: int
    werte: list[EroeffnungWert] = Field(max_length=60)


@router.put("/eroeffnung")
def eroeffnung_speichern(body: EroeffnungIn, user: dict = Depends(get_current_user),
                         db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    _nur_bilanz(db, body.gewerbe_id, body.jahr)
    if gw.erstes_bilanzjahr(db, body.gewerbe_id, body.jahr) != body.jahr:
        raise HTTPException(400, "Eröffnungswerte gibt es nur im ersten Bilanz-Jahr; danach gilt der Schlussbestand des Vorjahres.")
    erlaubt = set(bz.EROEFFNUNG_AKTIV) | set(bz.EROEFFNUNG_PASSIV)
    gesehen = set()
    for w in body.werte:
        if w.posten in gesehen:
            raise HTTPException(400, f"Posten {w.posten} doppelt.")
        gesehen.add(w.posten)
        if w.posten not in erlaubt and not (w.posten.startswith("bank:") and bz.konto_gueltig(db, body.gewerbe_id, w.posten)):
            raise HTTPException(400, f"Unbekannter Posten: {w.posten}")
    db.execute("DELETE FROM bilanz_eroeffnung WHERE gewerbe_id = ? AND jahr = ?", (body.gewerbe_id, body.jahr))
    for w in body.werte:
        if w.betrag_cent:
            db.execute("INSERT INTO bilanz_eroeffnung (gewerbe_id, jahr, posten, betrag_cent, text) VALUES (?,?,?,?,?)",
                       (body.gewerbe_id, body.jahr, w.posten, w.betrag_cent, (w.text or "").strip() or None))
    db.commit()
    return {"ok": True}


# ── Abschlussbuchungen ───────────────────────────────────────────────────────

class AbschlussIn(BaseModel):
    gewerbe_id: int
    datum: str
    soll: str
    haben: str
    betrag_cent: int = Field(gt=0)
    text: str | None = Field(default=None, max_length=300)

    @field_validator("datum")
    @classmethod
    def _datum(cls, v: str) -> str:
        import datetime as dt
        dt.date.fromisoformat(v)
        return v


@router.post("/abschlussbuchungen", status_code=201)
def abschluss_anlegen(body: AbschlussIn, user: dict = Depends(get_current_user),
                      db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    _nur_bilanz(db, body.gewerbe_id, int(body.datum[:4]))
    for k in (body.soll, body.haben):
        if not bz.konto_gueltig(db, body.gewerbe_id, k):
            raise HTTPException(400, f"Unbekanntes Konto: {k}")
    if body.soll == body.haben:
        raise HTTPException(400, "Soll und Haben müssen verschieden sein.")
    cur = db.execute(
        "INSERT INTO abschlussbuchung (gewerbe_id, datum, soll, haben, betrag_cent, text) VALUES (?,?,?,?,?,?)",
        (body.gewerbe_id, body.datum, body.soll, body.haben, body.betrag_cent, (body.text or "").strip() or None))
    db.commit()
    return {"id": cur.lastrowid}


@router.delete("/abschlussbuchungen/{abschluss_id}", status_code=204)
def abschluss_loeschen(abschluss_id: int, user: dict = Depends(get_current_user),
                       db: sqlite3.Connection = Depends(get_db)):
    r = db.execute("SELECT gewerbe_id FROM abschlussbuchung WHERE id = ?", (abschluss_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Nicht gefunden.")
    check_gewerbe(db, user, r["gewerbe_id"])
    db.execute("DELETE FROM abschlussbuchung WHERE id = ?", (abschluss_id,))
    db.commit()
    return Response(status_code=204)
