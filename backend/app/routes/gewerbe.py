"""Gewerbe-Verwaltung: anlegen, umbenennen, (de)aktivieren. Kein Löschen."""
from __future__ import annotations

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user, ist_admin
from ..db import get_db
from ..services import besteuerung as best
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
    ust_id: str | None = Field(default=None, max_length=20)

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
    anschrift: str | None = None
    iban: str | None = None
    kontoinhaber: str | None = Field(default=None, max_length=70)
    rechnung_fusszeile: str | None = None
    ust_id: str | None = Field(default=None, max_length=20)
    # Umsatzsteuer-Voranmeldung (v35)
    ustva_zeitraum: str | None = Field(default=None, pattern="^(monat|quartal|jahr)$")
    ustva_dauerfrist: bool | None = None
    # Zahlung & Mahnwesen (v17)
    zahlungsziel_tage: int | None = Field(default=None, ge=0, le=120)
    mahn_frist_tage: int | None = Field(default=None, ge=1, le=90)
    mahn_gebuehr_1_cent: int | None = Field(default=None, ge=0, le=100_000)
    mahn_gebuehr_2_cent: int | None = Field(default=None, ge=0, le=100_000)
    mahn_gebuehr_3_cent: int | None = Field(default=None, ge=0, le=100_000)
    # Basispunkte (127 = 1,27 %); explizit null = keine Verzugszinsen -> model_fields_set
    basiszinssatz_bp: int | None = Field(default=None, ge=-1_000, le=2_000)


class BesteuerungIn(BaseModel):
    """Wechsel der Besteuerung zum 1.1. von `ab_jahr` (EUER_KATEGORIEN.md §8)."""
    ab_jahr: int = Field(ge=2000, le=2100)
    art: str

    @field_validator("art")
    @classmethod
    def _v_art(cls, v: str) -> str:
        if v not in BESTEUERUNG:
            raise ValueError("art muss 'kleinunternehmer' oder 'regelbesteuerung' sein.")
        return v


def _ausgabe(row: sqlite3.Row, db: sqlite3.Connection | None = None) -> dict:
    """Gewerbe für die API: der Logo-Dateiname bleibt intern, nach außen nur „hat_logo“.
    `besteuerung_wechsel` = Liste der Wechsel; die Art eines Jahres rechnet das Frontend daraus
    (lib/besteuerung.js, gleiche Regel wie services/besteuerung.art)."""
    d = dict(row)
    d["hat_logo"] = logo_svc.logo_pfad(row) is not None
    d.pop("logo_datei", None)
    if db is not None:
        d["besteuerung_wechsel"] = best.wechsel(db, row["id"])
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
    return [_ausgabe(r, db) for r in db.execute(sql, (user["email"],)).fetchall()]


@router.post("", status_code=201)
def create_gewerbe(
    body: GewerbeIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute(
        "INSERT INTO gewerbe (name, steuernummer, besteuerung, anschrift, iban, kontoinhaber, "
        "rechnung_fusszeile, ust_id, owner_email) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            body.name.strip(),
            (body.steuernummer or "").strip() or None,
            body.besteuerung,
            (body.anschrift or "").strip() or None,
            (body.iban or "").strip() or None,
            (body.kontoinhaber or "").strip() or None,
            (body.rechnung_fusszeile or "").strip() or None,
            (body.ust_id or "").strip().upper().replace(" ", "") or None,
            user["email"],
        ),
    )
    if body.besteuerung == best.REGEL:
        # Neues Gewerbe mit Regelbesteuerung: gilt ab dem laufenden Jahr
        db.execute(
            "INSERT INTO gewerbe_besteuerung (gewerbe_id, ab_jahr, art) VALUES (?, ?, ?)",
            (cur.lastrowid, dt.date.today().year, best.REGEL),
        )
    db.commit()
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (cur.lastrowid,)).fetchone(), db)


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
    if body.ust_id is not None:
        fields.append("ust_id = ?"); values.append(body.ust_id.strip().upper().replace(" ", "") or None)
    if body.ustva_zeitraum is not None:
        fields.append("ustva_zeitraum = ?"); values.append(body.ustva_zeitraum)
    if body.ustva_dauerfrist is not None:
        fields.append("ustva_dauerfrist = ?"); values.append(1 if body.ustva_dauerfrist else 0)
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
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone(), db)


# ── Besteuerung je Jahr (Regelbesteuerung als Option, v34) ───────────────────

def _pruefe_wechsel(db: sqlite3.Connection, gewerbe_id: int, ab_jahr: int, neu: dict[int, str]) -> None:
    """Ein Wechsel betrifft alle Jahre ab `ab_jahr`. Nicht erlaubt, wenn eines davon abgeschlossen ist oder
    Buchungen hat, die zur neuen Art nicht passen (USt in einem KU-Jahr, KU-Kategorie in einem Regel-Jahr)."""
    gesperrt = db.execute(
        "SELECT MIN(jahr) AS j FROM jahr_abschluss WHERE gewerbe_id = ? AND abgeschlossen = 1 AND jahr >= ?",
        (gewerbe_id, ab_jahr),
    ).fetchone()["j"]
    if gesperrt is not None:
        raise HTTPException(400, f"Das Jahr {gesperrt} ist abgeschlossen — die Besteuerung lässt sich dafür nicht mehr ändern.")

    def art_fuer(jahr: int) -> str:
        passend = [j for j in neu if j <= jahr]
        return neu[max(passend)] if passend else best.KU

    for r in db.execute(
        "SELECT CAST(substr(b.datum,1,4) AS INTEGER) AS jahr, "
        "SUM(CASE WHEN p.ust_cent > 0 OR p.ust_bp > 0 OR k.nur_besteuerung = 'regelbesteuerung' THEN 1 ELSE 0 END) AS regel, "
        "SUM(CASE WHEN k.nur_besteuerung = 'kleinunternehmer' THEN 1 ELSE 0 END) AS ku "
        "FROM buchung b JOIN buchung_position p ON p.buchung_id = b.id JOIN kategorie k ON k.id = p.kategorie_id "
        "WHERE b.gewerbe_id = ? AND b.datum >= ? GROUP BY 1 ORDER BY 1",
        (gewerbe_id, f"{ab_jahr:04d}-01-01"),
    ):
        art = art_fuer(r["jahr"])
        if art == best.KU and r["regel"]:
            raise HTTPException(
                409, f"{r['jahr']} hat {r['regel']} Buchungsposition(en) mit Umsatzsteuer — als Kleinunternehmer geht das nicht. "
                "Erst diese Buchungen ändern."
            )
        if art == best.REGEL and r["ku"]:
            raise HTTPException(
                409, f"{r['jahr']} hat {r['ku']} Buchungsposition(en) mit „Einnahme Kleinunternehmer“. Bei Regelbesteuerung "
                "gehören sie in „Umsatzsteuerpflichtige Einnahme“ mit Steuersatz — erst diese Buchungen ändern."
            )


@router.put("/{gewerbe_id}/besteuerung")
def besteuerung_setzen(
    gewerbe_id: int, body: BesteuerungIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    """Ab dem 1.1. von `ab_jahr` gilt `art` (bis zum nächsten Wechsel)."""
    check_gewerbe(db, user, gewerbe_id)
    neu = {w["ab_jahr"]: w["art"] for w in best.wechsel(db, gewerbe_id)}
    neu[body.ab_jahr] = body.art
    _pruefe_wechsel(db, gewerbe_id, body.ab_jahr, neu)
    db.execute(
        "INSERT INTO gewerbe_besteuerung (gewerbe_id, ab_jahr, art) VALUES (?, ?, ?) "
        "ON CONFLICT(gewerbe_id, ab_jahr) DO UPDATE SET art = excluded.art",
        (gewerbe_id, body.ab_jahr, body.art),
    )
    best.sync_aktuell(db, gewerbe_id)
    db.commit()
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone(), db)


@router.delete("/{gewerbe_id}/besteuerung/{ab_jahr}")
def besteuerung_entfernen(
    gewerbe_id: int, ab_jahr: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    check_gewerbe(db, user, gewerbe_id)
    neu = {w["ab_jahr"]: w["art"] for w in best.wechsel(db, gewerbe_id)}
    if ab_jahr not in neu:
        raise HTTPException(404, "Diesen Wechsel gibt es nicht.")
    del neu[ab_jahr]
    _pruefe_wechsel(db, gewerbe_id, ab_jahr, neu)
    db.execute("DELETE FROM gewerbe_besteuerung WHERE gewerbe_id = ? AND ab_jahr = ?", (gewerbe_id, ab_jahr))
    best.sync_aktuell(db, gewerbe_id)
    db.commit()
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone(), db)


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
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone(), db)


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
    return _ausgabe(db.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone(), db)
