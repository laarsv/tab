"""Rechnungs-Abos (wiederkehrende Rechnungen): CRUD + „Jetzt ausführen".

Absender = der Login, der das Abo anlegt (dessen App-Passwort wird beim
Auto-Versand genutzt). Ohne hinterlegtes App-Passwort bleibt die erzeugte
Rechnung als Entwurf liegen — kein Fehler, kein Datenverlust."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import get_current_user
from ..db import get_db
from ..services.abo import INTERVALL_MONATE, erstelle_rechnung_aus_abo, naechster_termin
from ..services.mailer import is_configured
from ..services.rechnung_pdf import STEUERHINWEISE
from .kontakte import upsert_kontakt

router = APIRouter(prefix="/api/rechnungsabos", tags=["rechnungsabos"])


class AboPositionIn(BaseModel):
    beschreibung: str = Field(min_length=1, max_length=500)
    menge: float = Field(gt=0, le=100000)
    einzelpreis_cent: int = Field(gt=0)


class AboIn(BaseModel):
    gewerbe_id: int
    empfaenger_name: str = Field(min_length=1, max_length=200)
    empfaenger_anschrift: str | None = None
    empfaenger_email: str | None = None
    notiz: str | None = None
    steuerhinweis: str = "ku19"
    intervall: str
    naechste_am: str
    auto_senden: bool = False
    betreff: str | None = Field(default=None, max_length=200)
    mail_text: str | None = Field(default=None, max_length=5000)
    positionen: list[AboPositionIn] = Field(min_length=1)

    @field_validator("naechste_am")
    @classmethod
    def _v_date(cls, v: str) -> str:
        try:
            dt.date.fromisoformat(v)
        except ValueError:
            raise ValueError("naechste_am muss im Format YYYY-MM-DD sein.")
        return v

    @field_validator("intervall")
    @classmethod
    def _v_intervall(cls, v: str) -> str:
        if v not in INTERVALL_MONATE:
            raise ValueError(f"intervall muss einer von {sorted(INTERVALL_MONATE)} sein.")
        return v

    @field_validator("steuerhinweis")
    @classmethod
    def _v_hinweis(cls, v: str) -> str:
        if v not in STEUERHINWEISE:
            raise ValueError(f"steuerhinweis muss einer von {sorted(STEUERHINWEISE)} sein.")
        return v


class AboPatch(AboIn):
    # Alle Felder optional; gewerbe_id bleibt fix.
    gewerbe_id: int | None = None
    empfaenger_name: str | None = Field(default=None, min_length=1, max_length=200)
    intervall: str | None = None
    naechste_am: str | None = None
    auto_senden: bool | None = None
    steuerhinweis: str | None = None
    positionen: list[AboPositionIn] | None = None
    aktiv: bool | None = None

    @field_validator("naechste_am")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                dt.date.fromisoformat(v)
            except ValueError:
                raise ValueError("naechste_am muss im Format YYYY-MM-DD sein.")
        return v

    @field_validator("intervall")
    @classmethod
    def _v_intervall(cls, v: str | None) -> str | None:
        if v is not None and v not in INTERVALL_MONATE:
            raise ValueError(f"intervall muss einer von {sorted(INTERVALL_MONATE)} sein.")
        return v

    @field_validator("steuerhinweis")
    @classmethod
    def _v_hinweis(cls, v: str | None) -> str | None:
        if v is not None and v not in STEUERHINWEISE:
            raise ValueError(f"steuerhinweis muss einer von {sorted(STEUERHINWEISE)} sein.")
        return v


def _row(db: sqlite3.Connection, abo_id: int) -> dict:
    r = db.execute("SELECT * FROM rechnung_abo WHERE id = ?", (abo_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Abo nicht gefunden.")
    d = dict(r)
    d["positionen"] = json.loads(d.pop("positionen_json"))
    d["summe_cent"] = sum(round(p["menge"] * p["einzelpreis_cent"]) for p in d["positionen"])
    d["absender_konfiguriert"] = is_configured(db, d["absender_email"])
    return d


@router.get("", dependencies=[Depends(get_current_user)])
def list_abos(gewerbe_id: int, db: sqlite3.Connection = Depends(get_db)):
    ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM rechnung_abo WHERE gewerbe_id = ? ORDER BY naechste_am, id",
            (gewerbe_id,),
        )
    ]
    return [_row(db, i) for i in ids]


@router.post("", status_code=201)
def create_abo(
    body: AboIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    if db.execute("SELECT 1 FROM gewerbe WHERE id = ?", (body.gewerbe_id,)).fetchone() is None:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    if body.auto_senden and not (body.empfaenger_email or "").strip():
        raise HTTPException(400, "Auto-Versand braucht eine Empfänger-E-Mail.")
    cur = db.execute(
        """
        INSERT INTO rechnung_abo (gewerbe_id, empfaenger_name, empfaenger_anschrift,
            empfaenger_email, notiz, steuerhinweis, positionen_json, intervall,
            naechste_am, auto_senden, betreff, mail_text, absender_email)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            body.gewerbe_id,
            body.empfaenger_name.strip(),
            (body.empfaenger_anschrift or "").strip() or None,
            (body.empfaenger_email or "").strip() or None,
            (body.notiz or "").strip() or None,
            body.steuerhinweis,
            json.dumps([p.model_dump() for p in body.positionen]),
            body.intervall,
            body.naechste_am,
            1 if body.auto_senden else 0,
            (body.betreff or "").strip() or None,
            (body.mail_text or "").strip() or None,
            user["email"],
        ),
    )
    upsert_kontakt(db, body.gewerbe_id, body.empfaenger_name,
                   body.empfaenger_anschrift, body.empfaenger_email)
    db.commit()
    return _row(db, cur.lastrowid)


@router.patch("/{abo_id}", dependencies=[Depends(get_current_user)])
def update_abo(abo_id: int, body: AboPatch, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT 1 FROM rechnung_abo WHERE id = ?", (abo_id,)).fetchone() is None:
        raise HTTPException(404, "Abo nicht gefunden.")
    fields, values = [], []
    if body.empfaenger_name is not None:
        fields.append("empfaenger_name = ?"); values.append(body.empfaenger_name.strip())
    for col, val in [
        ("empfaenger_anschrift", body.empfaenger_anschrift),
        ("empfaenger_email", body.empfaenger_email),
        ("notiz", body.notiz),
        ("betreff", body.betreff),
        ("mail_text", body.mail_text),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val.strip() or None)
    for col, val in [
        ("steuerhinweis", body.steuerhinweis),
        ("intervall", body.intervall),
        ("naechste_am", body.naechste_am),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val)
    if body.auto_senden is not None:
        fields.append("auto_senden = ?"); values.append(1 if body.auto_senden else 0)
    if body.aktiv is not None:
        fields.append("aktiv = ?"); values.append(1 if body.aktiv else 0)
    if body.positionen is not None:
        fields.append("positionen_json = ?")
        values.append(json.dumps([p.model_dump() for p in body.positionen]))
    if fields:
        fields.append("updated_at = datetime('now')")
        db.execute(f"UPDATE rechnung_abo SET {', '.join(fields)} WHERE id = ?", (*values, abo_id))
        db.commit()
    return _row(db, abo_id)


@router.delete("/{abo_id}", status_code=204, dependencies=[Depends(get_current_user)])
def delete_abo(abo_id: int, db: sqlite3.Connection = Depends(get_db)):
    db.execute("DELETE FROM rechnung_abo WHERE id = ?", (abo_id,))
    db.commit()


@router.post("/{abo_id}/run", dependencies=[Depends(get_current_user)])
def run_abo(abo_id: int, db: sqlite3.Connection = Depends(get_db)):
    """Jetzt ausführen: erstellt sofort die Rechnung für den nächsten Stichtag
    (versendet ggf. automatisch) und schiebt den Stichtag weiter."""
    abo = db.execute("SELECT * FROM rechnung_abo WHERE id = ?", (abo_id,)).fetchone()
    if abo is None:
        raise HTTPException(404, "Abo nicht gefunden.")
    heute = dt.date.today()
    stichtag = min(dt.date.fromisoformat(abo["naechste_am"]), heute)
    ergebnis = erstelle_rechnung_aus_abo(db, abo, stichtag, heute)
    neuer = naechster_termin(dt.date.fromisoformat(abo["naechste_am"]), abo["intervall"])
    db.execute(
        "UPDATE rechnung_abo SET naechste_am = ?, updated_at = datetime('now') WHERE id = ?",
        (neuer.isoformat(), abo_id),
    )
    db.commit()
    return {**ergebnis, "abo": _row(db, abo_id)}
