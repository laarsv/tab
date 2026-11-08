"""Dauerbelege: Vorlagen für Ausgaben in festen Abständen (Miete, Versicherung, Leasing, Abos).

Aufbau nach Haben (Vorlage einmal anlegen, Termine entstehen fällig, Änderungen gelten für künftige
Termine, Pausieren/Beenden, nie von selbst buchen), eigenständig auf Tabs EÜR zugeschnitten:
gebucht wird der Zahlungsfluss, ein fälliger Termin wird mit einem Klick zur Buchung. Die Buchung selbst
läuft über `POST /api/buchungen` (mit `dauerbeleg_id` + `termin`, wie Rechnung und Bank-Zuordnung) —
hier steht nur die Vorlage samt „Alle fälligen buchen“ und „Überspringen“. Details: services/dauerbelege.py.
"""
from __future__ import annotations

import calendar
import datetime as dt
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services import dauerbelege as dsvc
from ..services.audit import SPERR_PRAEFIX
from ..services.privatanteil import betrieblich_cent

router = APIRouter(prefix="/api/dauerbelege", tags=["dauerbelege"], dependencies=[Depends(get_current_user)])

Intervall = Literal["monatlich", "vierteljaehrlich", "halbjaehrlich", "jaehrlich"]


def _valid_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("Datum muss im Format YYYY-MM-DD sein.")
    return value


class DauerIn(BaseModel):
    gewerbe_id: int
    bezeichnung: str = Field(min_length=1, max_length=120)
    notiz: str | None = Field(default=None, max_length=500)
    kategorie_id: int
    betrag_cent: int = Field(gt=0)
    privat_bp: int = Field(default=0, ge=0, le=10000)
    intervall: Intervall = "monatlich"
    naechste_am: str  # erster Termin
    endet_am: str | None = None

    @field_validator("naechste_am", "endet_am")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


class DauerPatch(BaseModel):
    bezeichnung: str | None = Field(default=None, min_length=1, max_length=120)
    notiz: str | None = Field(default=None, max_length=500)
    kategorie_id: int | None = None
    betrag_cent: int | None = Field(default=None, gt=0)
    privat_bp: int | None = Field(default=None, ge=0, le=10000)
    intervall: Intervall | None = None
    naechste_am: str | None = None
    endet_am: str | None = None  # null löscht das Ende (model_fields_set)
    aktiv: bool | None = None

    @field_validator("naechste_am", "endet_am")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


def _pruefe_kategorie(db: sqlite3.Connection, kategorie_id: int) -> None:
    k = db.execute("SELECT * FROM kategorie WHERE id = ?", (kategorie_id,)).fetchone()
    if k is None:
        raise HTTPException(404, "Kategorie nicht gefunden.")
    if k["typ"] != "ausgabe":
        raise HTTPException(400, "Ein Dauerbeleg ist eine Ausgabe — bitte eine Ausgabe-Kategorie wählen.")
    if k["ist_afa"]:
        raise HTTPException(400, "AfA-Kategorien gehören in die AfA-Erfassung, nicht in einen Dauerbeleg.")
    if k["belegpflicht_extra"]:
        raise HTTPException(
            400, f"Für „{k['name']}“ sind Beleg-Details Pflicht — das passt nicht zu einem Dauerbeleg. Bitte einzeln buchen."
        )


def _check(db: sqlite3.Connection, user: dict, dauerbeleg_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM dauerbeleg WHERE id = ?", (dauerbeleg_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Dauerbeleg nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    return row


def _row(db: sqlite3.Connection, dauerbeleg_id: int, heute: str) -> dict:
    r = db.execute(
        "SELECT d.*, k.name AS kategorie_name, "
        "(SELECT COUNT(*) FROM buchung b WHERE b.dauerbeleg_id = d.id) AS buchungen_anzahl, "
        "(SELECT MAX(b.datum) FROM buchung b WHERE b.dauerbeleg_id = d.id) AS letzte_buchung "
        "FROM dauerbeleg d JOIN kategorie k ON k.id = d.kategorie_id WHERE d.id = ?",
        (dauerbeleg_id,),
    ).fetchone()
    d = dict(r)
    d["aktiv"] = bool(d["aktiv"])
    d["beendet"] = dsvc.ist_beendet(r)
    d["faellige_termine"] = dsvc.faellige_termine(r, heute)
    d["betrieblich_cent"] = betrieblich_cent(r["betrag_cent"], r["privat_bp"])
    return d


@router.get("")
def liste(gewerbe_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, gewerbe_id)
    heute = dt.date.today().isoformat()
    ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM dauerbeleg WHERE gewerbe_id = ? ORDER BY aktiv DESC, bezeichnung COLLATE NOCASE", (gewerbe_id,)
        )
    ]
    return [_row(db, i, heute) for i in ids]


@router.get("/faellig")
def faellig(gewerbe_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Anzahl fälliger Termine (Zahl an „Dauerbelege“ in der Seitenleiste)."""
    check_gewerbe(db, user, gewerbe_id)
    return {"anzahl": dsvc.faellig_anzahl(db, gewerbe_id, dt.date.today().isoformat())}


@router.post("", status_code=201)
def anlegen(body: DauerIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    _pruefe_kategorie(db, body.kategorie_id)
    if body.endet_am and body.endet_am < body.naechste_am:
        raise HTTPException(400, "„Endet nach dem“ liegt vor dem ersten Termin.")
    cur = db.execute(
        "INSERT INTO dauerbeleg (gewerbe_id, bezeichnung, notiz, kategorie_id, betrag_cent, privat_bp, intervall, "
        "anker_tag, naechste_am, endet_am) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            body.gewerbe_id, body.bezeichnung.strip(), (body.notiz or "").strip() or None, body.kategorie_id,
            body.betrag_cent, body.privat_bp, body.intervall, int(body.naechste_am[8:10]), body.naechste_am,
            body.endet_am,
        ),
    )
    db.commit()
    return _row(db, cur.lastrowid, dt.date.today().isoformat())


@router.patch("/{dauerbeleg_id}")
def aendern(
    dauerbeleg_id: int, body: DauerPatch, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    """Änderungen gelten für künftige Termine; schon gebuchte Buchungen bleiben, wie sie sind."""
    cur = _check(db, user, dauerbeleg_id)
    if body.kategorie_id is not None:
        _pruefe_kategorie(db, body.kategorie_id)
    fields, values = [], []
    for col in ("bezeichnung", "kategorie_id", "betrag_cent", "privat_bp", "intervall"):
        val = getattr(body, col)
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val.strip() if isinstance(val, str) else val)
    if "notiz" in body.model_fields_set:
        fields.append("notiz = ?")
        values.append((body.notiz or "").strip() or None)
    naechste = cur["naechste_am"]
    if body.naechste_am is not None and body.naechste_am != cur["naechste_am"]:
        naechste = body.naechste_am
        # Neuer Termin = neuer Anker für den Tag im Monat — außer er ist nur der gekürzte alte Anker
        # (31. -> 30./28. im kurzen Monat): dann bleibt der Anker, sonst rutschte er beim Zurücksetzen ab.
        tag = int(naechste[8:10])
        monatslaenge = calendar.monthrange(int(naechste[:4]), int(naechste[5:7]))[1]
        anker = cur["anker_tag"] if tag == min(cur["anker_tag"], monatslaenge) else tag
        fields += ["naechste_am = ?", "anker_tag = ?"]
        values += [naechste, anker]
    if "endet_am" in body.model_fields_set:
        fields.append("endet_am = ?")
        values.append(body.endet_am)
    if body.aktiv is not None:
        fields.append("aktiv = ?")
        values.append(1 if body.aktiv else 0)
        if body.aktiv and not cur["aktiv"] and body.naechste_am is None:
            # Fortsetzen: beim ersten Termin ab heute, Termine aus der Pause werden nicht nachgeholt.
            # Wer sie doch will, setzt „Nächster Termin“ mit dem Fortsetzen zurück.
            t = cur["naechste_am"]
            heute = dt.date.today().isoformat()
            while t < heute:
                t = dsvc.termin_nach(t, body.intervall or cur["intervall"], cur["anker_tag"])
            if t != cur["naechste_am"]:
                fields.append("naechste_am = ?")
                values.append(t)
    if fields:
        fields.append("updated_at = datetime('now')")
        db.execute(f"UPDATE dauerbeleg SET {', '.join(fields)} WHERE id = ?", (*values, dauerbeleg_id))
        db.commit()
    return _row(db, dauerbeleg_id, dt.date.today().isoformat())


@router.delete("/{dauerbeleg_id}", status_code=204)
def loeschen(dauerbeleg_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM dauerbeleg WHERE id = ?", (dauerbeleg_id,)).fetchone()
    if cur is None:
        return
    check_gewerbe(db, user, cur["gewerbe_id"])
    if db.execute("SELECT 1 FROM buchung WHERE dauerbeleg_id = ?", (dauerbeleg_id,)).fetchone():
        raise HTTPException(409, "Aus diesem Dauerbeleg gibt es schon Buchungen — pausiere oder beende ihn stattdessen.")
    db.execute("DELETE FROM dauerbeleg WHERE id = ?", (dauerbeleg_id,))
    db.commit()


@router.post("/{dauerbeleg_id}/ueberspringen")
def ueberspringen(dauerbeleg_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Den nächsten fälligen Termin ohne Buchung abhaken (z. B. mietfreier Monat)."""
    cur = _check(db, user, dauerbeleg_id)
    heute = dt.date.today().isoformat()
    termine = dsvc.faellige_termine(cur, heute)
    if not termine:
        raise HTTPException(409, "Es ist kein Termin fällig.")
    dsvc.termin_verbrauchen(db, dauerbeleg_id, termine[0])
    db.commit()
    return _row(db, dauerbeleg_id, heute)


class FaelligeIn(BaseModel):
    gewerbe_id: int


@router.post("/faellige-buchen")
def faellige_buchen(body: FaelligeIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Alle fälligen Termine buchen: je Termin eine Buchung am Termintag mit der Vorlage (Betrag, Kategorie,
    Privatanteil). Gesperrte Jahre und andere Verstöße landen in `fehler`; die Vorlage bleibt dann an dem
    Termin stehen. Was schon gebucht ist, bleibt gebucht."""
    check_gewerbe(db, user, body.gewerbe_id)
    heute = dt.date.today().isoformat()
    gebucht, fehler = 0, []
    vorlagen = db.execute("SELECT * FROM dauerbeleg WHERE gewerbe_id = ? AND aktiv = 1 ORDER BY id", (body.gewerbe_id,)).fetchall()
    for v in vorlagen:
        for termin in dsvc.faellige_termine(v, heute):
            if db.execute("SELECT 1 FROM buchung WHERE dauerbeleg_id = ? AND termin = ?", (v["id"], termin)).fetchone():
                # Zeiger wurde zurückgesetzt, der Termin ist aber schon gebucht: nur weiterrücken
                dsvc.termin_verbrauchen(db, v["id"], termin)
                db.commit()
                continue
            try:
                cur = db.execute(
                    "INSERT INTO buchung (gewerbe_id, datum, beschreibung, dauerbeleg_id, termin) VALUES (?, ?, ?, ?, ?)",
                    (v["gewerbe_id"], termin, v["bezeichnung"], v["id"], termin),
                )
                db.execute(
                    "INSERT INTO buchung_position (buchung_id, kategorie_id, betrag_cent, privat_bp) VALUES (?, ?, ?, ?)",
                    (cur.lastrowid, v["kategorie_id"], v["betrag_cent"], v["privat_bp"]),
                )
                dsvc.termin_verbrauchen(db, v["id"], termin)
                db.commit()
                gebucht += 1
            except sqlite3.IntegrityError as e:
                db.rollback()
                text = str(e)
                if not text.startswith(SPERR_PRAEFIX):
                    raise
                meldung = text.split(": ", 1)[1]
                fehler.append({"dauerbeleg_id": v["id"], "bezeichnung": v["bezeichnung"], "termin": termin, "meldung": meldung})
                break
    return {"gebucht": gebucht, "fehler": fehler}
