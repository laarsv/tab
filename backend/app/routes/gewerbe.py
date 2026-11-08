"""Gewerbe-Verwaltung: anlegen, umbenennen, (de)aktivieren. Kein Löschen."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user, ist_admin
from ..db import get_db
from ..services import logo as logo_svc

router = APIRouter(prefix="/api/gewerbe", tags=["gewerbe"], dependencies=[Depends(get_current_user)])


BESTEUERUNG = {"kleinunternehmer", "regelbesteuerung"}


class GewerbeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    steuernummer: str | None = None
    besteuerung: str = "kleinunternehmer"
    anschrift: str | None = None          # Rechnungs-Absender (Name + Adresse, mehrzeilig)
    iban: str | None = None
    kontoinhaber: str | None = Field(default=None, max_length=70)  # GiroCode/BT-85; leer = Anschrift
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
    kontoinhaber: str | None = Field(default=None, max_length=70)
    rechnung_fusszeile: str | None = None
    # Zahlung & Mahnwesen (v17)
    zahlungsziel_tage: int | None = Field(default=None, ge=0, le=120)
    mahn_frist_tage: int | None = Field(default=None, ge=1, le=90)
    mahn_gebuehr_1_cent: int | None = Field(default=None, ge=0, le=100_000)
    mahn_gebuehr_2_cent: int | None = Field(default=None, ge=0, le=100_000)
    mahn_gebuehr_3_cent: int | None = Field(default=None, ge=0, le=100_000)
    # Basispunkte (127 = 1,27 %); explizit null = keine Verzugszinsen -> model_fields_set
    basiszinssatz_bp: int | None = Field(default=None, ge=-1_000, le=2_000)

    @field_validator("besteuerung")
    @classmethod
    def _v_best(cls, v: str | None) -> str | None:
        if v is not None and v not in BESTEUERUNG:
            raise ValueError("besteuerung muss 'kleinunternehmer' oder 'regelbesteuerung' sein.")
        return v


def _ausgabe(row: sqlite3.Row) -> dict:
    """Gewerbe für die API: der Logo-Dateiname bleibt intern, nach außen nur „hat_logo“."""
    d = dict(row)
    d["hat_logo"] = logo_svc.logo_pfad(row) is not None
    d.pop("logo_datei", None)
    return d


@router.get("")
def list_gewerbe(
    include_inactive: bool = False,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    sichtbar = "(owner_email = ? OR owner_email IS NULL)" if ist_admin(user) else "owner_email = ?"
    sql = f"SELECT * FROM gewerbe WHERE {sichtbar}"
    if not include_inactive:
        sql += " AND aktiv = 1"
    sql += " ORDER BY aktiv DESC, name COLLATE NOCASE"
    return [_ausgabe(r) for r in db.execute(sql, (user["email"],))]


@router.post("", status_code=201)
def create_gewerbe(
    body: GewerbeIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute(
        "INSERT INTO gewerbe (name, steuernummer, besteuerung, anschrift, iban, kontoinhaber, "
        "rechnung_fusszeile, owner_email) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            body.name.strip(),
            (body.steuernummer or "").strip() or None,
            body.besteuerung,
            (body.anschrift or "").strip() or None,
            (body.iban or "").strip() or None,
            (body.kontoinhaber or "").strip() or None,
            (body.rechnung_fusszeile or "").strip() or None,
            user["email"],
        ),
    )
    db.commit()
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.patch("/{gewerbe_id}")
def update_gewerbe(
    gewerbe_id: int,
    body: GewerbePatch,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
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
        ("kontoinhaber", body.kontoinhaber),
        ("rechnung_fusszeile", body.rechnung_fusszeile),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val.strip() or None)
    for col, val in [
        ("zahlungsziel_tage", body.zahlungsziel_tage),
        ("mahn_frist_tage", body.mahn_frist_tage),
        ("mahn_gebuehr_1_cent", body.mahn_gebuehr_1_cent),
        ("mahn_gebuehr_2_cent", body.mahn_gebuehr_2_cent),
        ("mahn_gebuehr_3_cent", body.mahn_gebuehr_3_cent),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val)
    if "basiszinssatz_bp" in body.model_fields_set:
        fields.append("basiszinssatz_bp = ?"); values.append(body.basiszinssatz_bp)
    if fields:
        fields.append("updated_at = datetime('now')")
        db.execute(f"UPDATE gewerbe SET {', '.join(fields)} WHERE id = ?", (*values, gewerbe_id))
        db.commit()
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone())


# ── Logo (Rechnung, Mahnung, Angebot) ───────────────────────────────────────

@router.post("/{gewerbe_id}/logo")
def logo_hochladen(
    gewerbe_id: int,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    try:
        logo_svc.speichere_logo(db, gewerbe_id, file.file.read(logo_svc.MAX_LOGO_BYTES + 1))
    except logo_svc.LogoAbgelehnt as e:
        raise HTTPException(400, str(e))
    db.commit()
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone())


@router.get("/{gewerbe_id}/logo")
def logo_ansehen(gewerbe_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    row = check_gewerbe(db, user, gewerbe_id)
    pfad = logo_svc.logo_pfad(row)
    if pfad is None:
        raise HTTPException(404, "Kein Logo hinterlegt.")
    return FileResponse(pfad, media_type="image/png", headers={"Cache-Control": "no-cache"})


@router.delete("/{gewerbe_id}/logo")
def logo_entfernen(gewerbe_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, gewerbe_id)
    logo_svc.loesche_logo(db, gewerbe_id)
    db.commit()
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone())
