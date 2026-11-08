"""AfA-Wirtschaftsgüter CRUD. Jahres-AfA wird berechnet (services/afa.py).

Methoden: linear (Standard), degressiv, Elektrofahrzeug, Sammelposten. Ob eine Methode für eine
Anschaffung zulässig ist, entscheidet allein `services/afa.py` (`optionen`/`degressiv_grenze`); das
Formular fragt `GET /optionen` und zeigt mit `POST /vorschau` den Plan vor dem Speichern.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services import afa as svc

router = APIRouter(prefix="/api/afa", tags=["afa"], dependencies=[Depends(get_current_user)])

Methode = Literal["linear", "degressiv", "elektro", "sammelposten"]


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
    afa_methode: Methode = "linear"
    degressiv_bp: int | None = Field(default=None, gt=0, le=3000)  # leer = Höchstsatz
    linear_ab_jahr: int | None = Field(default=None, ge=2000, le=2200)

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
    afa_methode: Methode | None = None
    degressiv_bp: int | None = Field(default=None, gt=0, le=3000)
    linear_ab_jahr: int | None = Field(default=None, ge=2000, le=2200)  # explizit null = kein früherer Wechsel

    @field_validator("anschaffungsdatum", "abgang_datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


class VorschauIn(BaseModel):
    anschaffungskosten_cent: int = Field(gt=0)
    anschaffungsdatum: str
    nutzungsdauer_jahre: int = Field(ge=1, le=50)
    abgang_datum: str | None = None
    afa_methode: Methode = "linear"
    degressiv_bp: int | None = Field(default=None, gt=0, le=3000)
    linear_ab_jahr: int | None = Field(default=None, ge=2000, le=2200)

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


def _normalisiere(
    datum: str, nd: int, methode: str, bp: int | None, linear_ab: int | None
) -> tuple[int, str, int | None, int | None]:
    """Prüft die Methode gegen die Anschaffung und gibt (Nutzungsdauer, Methode, Satz, Wechseljahr) zurück.

    Elektro und Sammelposten haben eine feste Dauer; degressiv ohne Satz nimmt den Höchstsatz."""
    jahr0 = int(datum[:4])
    if methode == "degressiv":
        max_bp, grund = svc.degressiv_grenze(datum, nd)
        if max_bp is None:
            raise HTTPException(400, grund)
        bp = bp or max_bp
        if bp > max_bp:
            raise HTTPException(
                400, f"Für diese Anschaffung sind höchstens {svc._prozent(max_bp)} % degressiv möglich."
            )
        if linear_ab is not None and not (jahr0 < linear_ab <= jahr0 + nd):
            raise HTTPException(400, f"„Linear ab Jahr“ muss zwischen {jahr0 + 1} und {jahr0 + nd} liegen.")
        return nd, "degressiv", bp, linear_ab
    if methode == "elektro":
        if not svc.elektro_moeglich(datum):
            raise HTTPException(
                400, "Die Elektro-Staffel gilt nur für Elektrofahrzeuge, die vom 01.07.2025 bis 31.12.2027 angeschafft wurden."
            )
        return svc.ELEKTRO_JAHRE, "elektro", None, None
    if methode == "sammelposten":
        return svc.SAMMELPOSTEN_JAHRE, "sammelposten", None, None
    return nd, "linear", None, None


def _hinweise(methode: str, ak_cent: int) -> list[str]:
    """Weiche Hinweise (kein Fehler): Sammelposten nur im Bereich 250,01–1.000 €, Wahlrecht je Wirtschaftsjahr."""
    out = []
    if methode == "sammelposten":
        if not (svc.SAMMELPOSTEN_VON_CENT <= ak_cent <= svc.SAMMELPOSTEN_BIS_CENT):
            out.append(
                "Ein Sammelposten ist nur für Anschaffungen von 250,01 bis 1.000 € vorgesehen "
                "(als Kleinunternehmer zählt der Betrag inklusive USt)."
            )
        out.append(
            "Das Wahlrecht gilt einheitlich für alle Anschaffungen dieses Jahres in diesem Bereich: "
            "Mit Sammelposten buchst du solche Güter im selben Jahr nicht als GWG."
        )
    return out


@router.get("/optionen")
def optionen(anschaffungsdatum: str, nutzungsdauer_jahre: int = 3):
    """Zulässige Methoden (und der degressive Höchstsatz) für eine Anschaffung."""
    try:
        _valid_date(anschaffungsdatum)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return svc.optionen(anschaffungsdatum, nutzungsdauer_jahre)


@router.post("/vorschau")
def vorschau(body: VorschauIn):
    """AfA-Plan je Jahr vor dem Speichern (nichts wird gespeichert)."""
    _check_abgang(body.anschaffungsdatum, body.abgang_datum)
    nd, methode, bp, lin = _normalisiere(
        body.anschaffungsdatum, body.nutzungsdauer_jahre, body.afa_methode, body.degressiv_bp, body.linear_ab_jahr
    )
    return {
        "nutzungsdauer_jahre": nd,
        "afa_methode": methode,
        "degressiv_bp": bp,
        "verlauf": svc.verlauf(
            body.anschaffungskosten_cent, body.anschaffungsdatum, nd, methode, bp, lin, body.abgang_datum
        ),
        "hinweise": _hinweise(methode, body.anschaffungskosten_cent),
    }


@router.get("")
def list_afa(
    gewerbe_id: int,
    jahr: int | None = None,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
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
            d["jahres_afa_cent"] = svc.afa_jahr(r, jahr)
        d["restbuchwert_cent"] = svc.afa_restbuchwert(r)
        d["methode_text"] = svc.methode_text(r)
        d["verlauf"] = svc.verlauf(
            r["anschaffungskosten_cent"], r["anschaffungsdatum"], r["nutzungsdauer_jahre"], r["afa_methode"],
            r["degressiv_bp"], r["linear_ab_jahr"], r["abgang_datum"],
        )
        out.append(d)
    return out


@router.post("", status_code=201)
def create_afa(
    body: AfaIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, body.gewerbe_id)
    _afa_kategorie(db, body.kategorie_id)
    _check_abgang(body.anschaffungsdatum, body.abgang_datum)
    nd, methode, bp, lin = _normalisiere(
        body.anschaffungsdatum, body.nutzungsdauer_jahre, body.afa_methode, body.degressiv_bp, body.linear_ab_jahr
    )
    cur = db.execute(
        """
        INSERT INTO afa_buchung
            (gewerbe_id, kategorie_id, bezeichnung, anschaffungskosten_cent,
             anschaffungsdatum, nutzungsdauer_jahre, abgang_datum, beschreibung,
             afa_methode, degressiv_bp, linear_ab_jahr)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            body.gewerbe_id,
            body.kategorie_id,
            body.bezeichnung.strip(),
            body.anschaffungskosten_cent,
            body.anschaffungsdatum,
            nd,
            body.abgang_datum,
            (body.beschreibung or "").strip() or None,
            methode,
            bp,
            lin,
        ),
    )
    db.commit()
    d = dict(db.execute("SELECT * FROM afa_buchung WHERE id = ?", (cur.lastrowid,)).fetchone())
    d["hinweise"] = _hinweise(methode, body.anschaffungskosten_cent)
    return d


@router.patch("/{afa_id}")
def update_afa(
    afa_id: int,
    body: AfaPatch,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM afa_buchung WHERE id = ?", (afa_id,)).fetchone()
    if cur is None:
        raise HTTPException(404, "AfA-Eintrag nicht gefunden.")
    check_gewerbe(db, user, cur["gewerbe_id"])
    if body.kategorie_id is not None:
        _afa_kategorie(db, body.kategorie_id)

    neues_anschaffung = body.anschaffungsdatum or cur["anschaffungsdatum"]
    if "abgang_datum" in body.model_fields_set:
        _check_abgang(neues_anschaffung, body.abgang_datum)
    elif body.anschaffungsdatum is not None:
        _check_abgang(neues_anschaffung, cur["abgang_datum"])

    # Methode samt Satz/Wechseljahr gegen die (neue) Anschaffung prüfen; Elektro/Sammelposten setzen die Dauer
    methode_neu = body.afa_methode or cur["afa_methode"] or "linear"
    nd_neu, methode_neu, bp_neu, lin_neu = _normalisiere(
        neues_anschaffung,
        body.nutzungsdauer_jahre or cur["nutzungsdauer_jahre"],
        methode_neu,
        body.degressiv_bp if "degressiv_bp" in body.model_fields_set else (
            cur["degressiv_bp"] if methode_neu == (cur["afa_methode"] or "linear") else None
        ),
        body.linear_ab_jahr if "linear_ab_jahr" in body.model_fields_set else (
            cur["linear_ab_jahr"] if methode_neu == (cur["afa_methode"] or "linear") else None
        ),
    )

    fields, values = [], []
    for col, val in [
        ("kategorie_id", body.kategorie_id),
        ("bezeichnung", body.bezeichnung.strip() if body.bezeichnung else None),
        ("anschaffungskosten_cent", body.anschaffungskosten_cent),
        ("anschaffungsdatum", body.anschaffungsdatum),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val)
    # Methode und Dauer immer mitschreiben (unveränderte Werte lösen den Sperr-Trigger nicht aus: IS NOT)
    fields += ["nutzungsdauer_jahre = ?", "afa_methode = ?", "degressiv_bp = ?", "linear_ab_jahr = ?"]
    values += [nd_neu, methode_neu, bp_neu, lin_neu]
    if "abgang_datum" in body.model_fields_set:  # explizit null = Abgang zurücknehmen
        fields.append("abgang_datum = ?"); values.append(body.abgang_datum)
    if body.beschreibung is not None:
        fields.append("beschreibung = ?"); values.append(body.beschreibung.strip() or None)
    fields.append("updated_at = datetime('now')")
    db.execute(f"UPDATE afa_buchung SET {', '.join(fields)} WHERE id = ?", (*values, afa_id))
    db.commit()
    d = dict(db.execute("SELECT * FROM afa_buchung WHERE id = ?", (afa_id,)).fetchone())
    d["hinweise"] = _hinweise(methode_neu, d["anschaffungskosten_cent"])
    return d


@router.delete("/{afa_id}", status_code=204)
def delete_afa(
    afa_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM afa_buchung WHERE id = ?", (afa_id,)).fetchone()
    if cur is not None:
        check_gewerbe(db, user, cur["gewerbe_id"])
    db.execute("DELETE FROM afa_buchung WHERE id = ?", (afa_id,))
    db.commit()
