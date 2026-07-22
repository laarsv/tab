"""Rechnungen (Kleinunternehmer, §19-Hinweis): CRUD, PDF, Mail-Versand, Status.

Nummer: fortlaufend je Gewerbe + Jahr ({jahr}-{lauf:04d}), vergeben beim Anlegen.
Löschen nur für die höchste Nummer eines Jahres (keine Lücken) und nicht nach
Versand/Bezahlung — sonst stornieren. Inhalt editierbar nur im Status 'entwurf'.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import get_current_user
from ..db import get_db
from ..services.e_rechnung import rechnungs_pdf
from ..services.mailer import MailNotConfiguredError, MailSendError, send_mail
from ..services.rechnung_pdf import STEUERHINWEISE
from ..services.rechnungen import erstelle_rechnung
from .kontakte import upsert_kontakt

router = APIRouter(prefix="/api/rechnungen", tags=["rechnungen"])


def _valid_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("datum muss im Format YYYY-MM-DD sein.")
    return value


class RPositionIn(BaseModel):
    beschreibung: str = Field(min_length=1, max_length=500)
    menge: float = Field(gt=0, le=100000)
    einzelpreis_cent: int = Field(gt=0)


class RechnungIn(BaseModel):
    gewerbe_id: int
    datum: str
    leistungsdatum: str | None = Field(default=None, max_length=80)
    empfaenger_name: str = Field(min_length=1, max_length=200)
    empfaenger_anschrift: str | None = None
    empfaenger_email: str | None = None
    notiz: str | None = None
    steuerhinweis: str = "ku19"
    positionen: list[RPositionIn] = Field(min_length=1)

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str) -> str:
        return _valid_date(v)

    @field_validator("steuerhinweis")
    @classmethod
    def _v_hinweis(cls, v: str) -> str:
        if v not in STEUERHINWEISE:
            raise ValueError(f"steuerhinweis muss einer von {sorted(STEUERHINWEISE)} sein.")
        return v


class RechnungPatch(BaseModel):
    datum: str | None = None
    leistungsdatum: str | None = Field(default=None, max_length=80)
    empfaenger_name: str | None = Field(default=None, min_length=1, max_length=200)
    empfaenger_anschrift: str | None = None
    empfaenger_email: str | None = None
    notiz: str | None = None
    steuerhinweis: str | None = None
    positionen: list[RPositionIn] | None = None

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v

    @field_validator("steuerhinweis")
    @classmethod
    def _v_hinweis(cls, v: str | None) -> str | None:
        if v is not None and v not in STEUERHINWEISE:
            raise ValueError(f"steuerhinweis muss einer von {sorted(STEUERHINWEISE)} sein.")
        return v


def _positionen(db: sqlite3.Connection, rechnung_id: int) -> list[dict]:
    return [
        dict(r)
        for r in db.execute(
            "SELECT * FROM rechnung_position WHERE rechnung_id = ? ORDER BY id", (rechnung_id,)
        )
    ]


def _row(db: sqlite3.Connection, rechnung_id: int) -> dict:
    r = db.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")
    d = dict(r)
    d["positionen"] = _positionen(db, rechnung_id)
    d["summe_cent"] = sum(round(p["menge"] * p["einzelpreis_cent"]) for p in d["positionen"])
    return d


@router.get("", dependencies=[Depends(get_current_user)])
def list_rechnungen(gewerbe_id: int, jahr: int, db: sqlite3.Connection = Depends(get_db)):
    ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM rechnung WHERE gewerbe_id = ? AND jahr = ? "
            "ORDER BY laufnummer DESC",
            (gewerbe_id, jahr),
        )
    ]
    return [_row(db, i) for i in ids]


@router.post("", status_code=201, dependencies=[Depends(get_current_user)])
def create_rechnung(body: RechnungIn, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT 1 FROM gewerbe WHERE id = ?", (body.gewerbe_id,)).fetchone() is None:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    rid = erstelle_rechnung(
        db,
        gewerbe_id=body.gewerbe_id,
        datum=body.datum,
        leistungsdatum=body.leistungsdatum,
        empfaenger_name=body.empfaenger_name,
        empfaenger_anschrift=body.empfaenger_anschrift,
        empfaenger_email=body.empfaenger_email,
        notiz=body.notiz,
        steuerhinweis=body.steuerhinweis,
        positionen=[p.model_dump() for p in body.positionen],
    )
    # Empfänger automatisch als Kontakt merken (füllt den Kontakte-Speicher von selbst).
    upsert_kontakt(db, body.gewerbe_id, body.empfaenger_name,
                   body.empfaenger_anschrift, body.empfaenger_email)
    db.commit()
    return _row(db, rid)


@router.patch("/{rechnung_id}", dependencies=[Depends(get_current_user)])
def update_rechnung(rechnung_id: int, body: RechnungPatch, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if cur is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")

    inhalt_geaendert = any(
        v is not None
        for v in (body.datum, body.leistungsdatum, body.empfaenger_name,
                  body.empfaenger_anschrift, body.steuerhinweis, body.positionen)
    )
    if inhalt_geaendert and cur["status"] != "entwurf":
        raise HTTPException(
            400, "Nur Entwürfe sind änderbar — versendete/bezahlte Rechnungen ggf. stornieren."
        )
    if body.datum is not None and int(body.datum[:4]) != cur["jahr"]:
        raise HTTPException(400, "Das Jahr einer Rechnung ist durch die Nummer fixiert.")

    fields, values = [], []
    for col, val in [
        ("datum", body.datum),
        ("empfaenger_name", body.empfaenger_name.strip() if body.empfaenger_name else None),
        ("steuerhinweis", body.steuerhinweis),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val)
    for col, val in [
        ("leistungsdatum", body.leistungsdatum),
        ("empfaenger_anschrift", body.empfaenger_anschrift),
        ("empfaenger_email", body.empfaenger_email),
        ("notiz", body.notiz),
    ]:
        if val is not None:
            fields.append(f"{col} = ?"); values.append(val.strip() or None)
    if fields:
        fields.append("updated_at = datetime('now')")
        db.execute(f"UPDATE rechnung SET {', '.join(fields)} WHERE id = ?", (*values, rechnung_id))
    if body.positionen is not None:
        db.execute("DELETE FROM rechnung_position WHERE rechnung_id = ?", (rechnung_id,))
        db.executemany(
            "INSERT INTO rechnung_position (rechnung_id, beschreibung, menge, einzelpreis_cent) "
            "VALUES (?, ?, ?, ?)",
            [(rechnung_id, p.beschreibung.strip(), p.menge, p.einzelpreis_cent) for p in body.positionen],
        )
    db.commit()
    return _row(db, rechnung_id)


@router.delete("/{rechnung_id}", status_code=204, dependencies=[Depends(get_current_user)])
def delete_rechnung(rechnung_id: int, db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if cur is None:
        return
    if cur["status"] in ("versendet", "bezahlt"):
        raise HTTPException(400, "Versendete/bezahlte Rechnungen nicht löschen — stornieren.")
    max_lauf = db.execute(
        "SELECT MAX(laufnummer) FROM rechnung WHERE gewerbe_id = ? AND jahr = ?",
        (cur["gewerbe_id"], cur["jahr"]),
    ).fetchone()[0]
    if cur["laufnummer"] != max_lauf:
        raise HTTPException(
            400,
            "Nur die letzte Rechnungsnummer kann gelöscht werden (fortlaufende Nummern, "
            "keine Lücken) — ältere Rechnungen stornieren.",
        )
    db.execute("DELETE FROM rechnung WHERE id = ?", (rechnung_id,))
    db.commit()


class StatusIn(BaseModel):
    status: str  # bezahlt | storniert | versendet | entwurf
    datum: str | None = None

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


@router.post("/{rechnung_id}/status", dependencies=[Depends(get_current_user)])
def set_status(rechnung_id: int, body: StatusIn, db: sqlite3.Connection = Depends(get_db)):
    if body.status not in ("entwurf", "versendet", "bezahlt", "storniert"):
        raise HTTPException(400, "Unbekannter Status.")
    cur = db.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if cur is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")
    heute = dt.date.today().isoformat()
    if body.status == "bezahlt":
        db.execute(
            "UPDATE rechnung SET status='bezahlt', bezahlt_am=?, updated_at=datetime('now') WHERE id=?",
            (body.datum or heute, rechnung_id),
        )
    elif body.status == "versendet":
        db.execute(
            "UPDATE rechnung SET status='versendet', versendet_am=COALESCE(versendet_am, ?), "
            "updated_at=datetime('now') WHERE id=?",
            (body.datum or heute, rechnung_id),
        )
    else:
        db.execute(
            "UPDATE rechnung SET status=?, updated_at=datetime('now') WHERE id=?",
            (body.status, rechnung_id),
        )
    db.commit()
    return _row(db, rechnung_id)


def _pdf_bytes(db: sqlite3.Connection, rechnung_id: int) -> tuple[bytes, dict]:
    r = _row(db, rechnung_id)
    g = db.execute("SELECT * FROM gewerbe WHERE id = ?", (r["gewerbe_id"],)).fetchone()
    return rechnungs_pdf(r, r["positionen"], g), r


@router.get("/{rechnung_id}/pdf", dependencies=[Depends(get_current_user)])
def rechnung_pdf(rechnung_id: int, db: sqlite3.Connection = Depends(get_db)):
    data, r = _pdf_bytes(db, rechnung_id)
    return Response(
        content=data,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="rechnung-{r["nummer"]}.pdf"'},
    )


class SendenIn(BaseModel):
    an: str = Field(min_length=3, max_length=200)
    betreff: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=5000)

    @field_validator("an")
    @classmethod
    def _v_mail(cls, v: str) -> str:
        v = v.strip()
        if "@" not in v or " " in v or "." not in v.split("@")[-1]:
            raise ValueError("Bitte eine gültige E-Mail-Adresse angeben.")
        return v


@router.post("/{rechnung_id}/senden")
def rechnung_senden(
    rechnung_id: int,
    body: SendenIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    data, r = _pdf_bytes(db, rechnung_id)
    if r["status"] == "storniert":
        raise HTTPException(400, "Stornierte Rechnungen nicht versenden.")
    try:
        send_mail(
            db,
            absender_email=user["email"],
            absender_name=user.get("name"),
            an=str(body.an),
            betreff=body.betreff.strip(),
            text=body.text,
            anhang=(f"rechnung-{r['nummer']}.pdf", data),
        )
    except (MailNotConfiguredError, MailSendError) as e:
        raise HTTPException(400, str(e))
    db.execute(
        "UPDATE rechnung SET status = CASE WHEN status='bezahlt' THEN status ELSE 'versendet' END, "
        "versendet_am = ?, empfaenger_email = ?, updated_at=datetime('now') WHERE id = ?",
        (dt.date.today().isoformat(), str(body.an), rechnung_id),
    )
    db.commit()
    return _row(db, rechnung_id)
