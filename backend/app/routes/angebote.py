"""Angebote (Kleinunternehmer): schreiben, als PDF/Mail senden, Antwort festhalten, in einen
Rechnungsentwurf umwandeln. Aufbau nach Haben (eigener Nummernkreis, optionale Positionen, Status
Entwurf/Offen/Abgelaufen/Angenommen/Abgelehnt/Abgerechnet), eigenständig und schlank:

  * Nummer `AN-{jahr}-{lauf:04d}` fortlaufend je Gewerbe + Jahr, vergeben beim Anlegen.
  * Positionen: normal (zählt zur Summe) oder optional (Zusatzleistung, nicht in der Summe).
  * Inhalt nur im Entwurf änderbar; ein versendetes Angebot lässt sich als neuer Entwurf kopieren.
  * „In Rechnung umwandeln“ (aus versendet/angenommen, einmal): Rechnungsentwurf mit den normalen
    und den gewählten optionalen Positionen; das Angebot gilt danach als angenommen und abgerechnet.
Angebote sind kein EÜR-Eintrag — die Jahres-Sperre betrifft sie nicht.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services.angebot_pdf import build_angebot_pdf
from ..services.fristen import add_days
from ..services.mailer import MailNotConfiguredError, MailSendError, send_mail
from ..services.rechnung_pdf import STEUERHINWEISE
from ..services.rechnungen import erstelle_rechnung
from .kontakte import upsert_kontakt

router = APIRouter(prefix="/api/angebote", tags=["angebote"])

GUELTIG_TAGE = 30


def _valid_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("Datum muss im Format YYYY-MM-DD sein.")
    return value


class APositionIn(BaseModel):
    beschreibung: str = Field(min_length=1, max_length=500)
    menge: float = Field(gt=0, le=100000)
    einzelpreis_cent: int = Field(gt=0)
    art: Literal["normal", "optional"] = "normal"


class AngebotIn(BaseModel):
    gewerbe_id: int
    datum: str
    gueltig_bis: str | None = None  # leer = Datum + 30 Tage
    empfaenger_name: str = Field(min_length=1, max_length=200)
    empfaenger_anschrift: str | None = None
    empfaenger_email: str | None = None
    einleitung: str | None = Field(default=None, max_length=2000)
    notiz: str | None = Field(default=None, max_length=2000)
    steuerhinweis: str = "ku19"
    positionen: list[APositionIn] = Field(min_length=1)

    @field_validator("datum", "gueltig_bis")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v

    @field_validator("steuerhinweis")
    @classmethod
    def _v_hinweis(cls, v: str) -> str:
        if v not in STEUERHINWEISE:
            raise ValueError(f"steuerhinweis muss einer von {sorted(STEUERHINWEISE)} sein.")
        return v


class AngebotPatch(BaseModel):
    datum: str | None = None
    gueltig_bis: str | None = None
    empfaenger_name: str | None = Field(default=None, min_length=1, max_length=200)
    empfaenger_anschrift: str | None = None
    empfaenger_email: str | None = None
    einleitung: str | None = Field(default=None, max_length=2000)
    notiz: str | None = Field(default=None, max_length=2000)
    steuerhinweis: str | None = None
    positionen: list[APositionIn] | None = Field(default=None, min_length=1)

    @field_validator("datum", "gueltig_bis")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v

    @field_validator("steuerhinweis")
    @classmethod
    def _v_hinweis(cls, v: str | None) -> str | None:
        if v is not None and v not in STEUERHINWEISE:
            raise ValueError(f"steuerhinweis muss einer von {sorted(STEUERHINWEISE)} sein.")
        return v


def _pruefe_positionen(positionen: list[APositionIn]) -> None:
    if not any(p.art == "normal" for p in positionen):
        raise HTTPException(400, "Mindestens eine Position muss zur Angebotssumme zählen (nicht nur optionale).")


def _check(db: sqlite3.Connection, user: dict, angebot_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM angebot WHERE id = ?", (angebot_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Angebot nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    return row


def _row(db: sqlite3.Connection, angebot_id: int) -> dict:
    d = dict(db.execute("SELECT * FROM angebot WHERE id = ?", (angebot_id,)).fetchone())
    d["positionen"] = [
        dict(p) for p in db.execute("SELECT * FROM angebot_position WHERE angebot_id = ? ORDER BY id", (angebot_id,))
    ]
    betrag = lambda p: round(p["menge"] * p["einzelpreis_cent"])
    d["summe_cent"] = sum(betrag(p) for p in d["positionen"] if p["art"] == "normal")
    d["optional_cent"] = sum(betrag(p) for p in d["positionen"] if p["art"] == "optional")
    # abgeleitet: abgelaufen = versendet ohne Antwort und Frist vorbei
    d["abgelaufen"] = d["status"] == "versendet" and d["gueltig_bis"] < dt.date.today().isoformat()
    rech = (
        db.execute("SELECT id, nummer, status FROM rechnung WHERE id = ?", (d["rechnung_id"],)).fetchone()
        if d["rechnung_id"] else None
    )
    d["rechnung"] = dict(rech) if rech else None
    return d


def _positionen_schreiben(db: sqlite3.Connection, angebot_id: int, positionen: list[APositionIn]) -> None:
    db.execute("DELETE FROM angebot_position WHERE angebot_id = ?", (angebot_id,))
    db.executemany(
        "INSERT INTO angebot_position (angebot_id, beschreibung, menge, einzelpreis_cent, art) VALUES (?, ?, ?, ?, ?)",
        [(angebot_id, p.beschreibung.strip(), p.menge, p.einzelpreis_cent, p.art) for p in positionen],
    )


@router.get("")
def liste(
    gewerbe_id: int,
    jahr: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM angebot WHERE gewerbe_id = ? AND jahr = ? ORDER BY laufnummer DESC", (gewerbe_id, jahr)
        )
    ]
    return [_row(db, i) for i in ids]


def _neu(db: sqlite3.Connection, gewerbe_id: int, datum: str, daten: dict, positionen: list[APositionIn]) -> int:
    jahr = int(datum[:4])
    lauf = (
        db.execute(
            "SELECT COALESCE(MAX(laufnummer), 0) FROM angebot WHERE gewerbe_id = ? AND jahr = ?", (gewerbe_id, jahr)
        ).fetchone()[0]
        + 1
    )
    cur = db.execute(
        """
        INSERT INTO angebot (gewerbe_id, jahr, laufnummer, nummer, datum, gueltig_bis, empfaenger_name,
                             empfaenger_anschrift, empfaenger_email, einleitung, notiz, steuerhinweis)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            gewerbe_id, jahr, lauf, f"AN-{jahr}-{lauf:04d}", datum, daten["gueltig_bis"],
            daten["empfaenger_name"].strip(), (daten.get("empfaenger_anschrift") or "").strip() or None,
            (daten.get("empfaenger_email") or "").strip() or None, (daten.get("einleitung") or "").strip() or None,
            (daten.get("notiz") or "").strip() or None, daten.get("steuerhinweis") or "ku19",
        ),
    )
    _positionen_schreiben(db, cur.lastrowid, positionen)
    return cur.lastrowid


@router.post("", status_code=201)
def anlegen(body: AngebotIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    _pruefe_positionen(body.positionen)
    gueltig = body.gueltig_bis or add_days(body.datum, GUELTIG_TAGE)
    if gueltig < body.datum:
        raise HTTPException(400, "„Gültig bis“ liegt vor dem Angebotsdatum.")
    aid = _neu(db, body.gewerbe_id, body.datum, {**body.model_dump(), "gueltig_bis": gueltig}, body.positionen)
    upsert_kontakt(db, body.gewerbe_id, body.empfaenger_name, body.empfaenger_anschrift, body.empfaenger_email)
    db.commit()
    return _row(db, aid)


@router.patch("/{angebot_id}")
def aendern(
    angebot_id: int, body: AngebotPatch, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    cur = _check(db, user, angebot_id)
    if cur["status"] != "entwurf":
        raise HTTPException(400, "Nur Entwürfe sind änderbar — ein versendetes Angebot lässt sich als neuer Entwurf kopieren.")
    if body.datum is not None and int(body.datum[:4]) != cur["jahr"]:
        raise HTTPException(400, "Das Jahr eines Angebots ist durch die Nummer fixiert.")
    datum = body.datum or cur["datum"]
    gueltig = body.gueltig_bis or cur["gueltig_bis"]
    if body.datum and not body.gueltig_bis:
        gueltig = add_days(datum, GUELTIG_TAGE)  # Datum verschoben: Gültigkeit mitnehmen
    if gueltig < datum:
        raise HTTPException(400, "„Gültig bis“ liegt vor dem Angebotsdatum.")
    fields, values = ["datum = ?", "gueltig_bis = ?"], [datum, gueltig]
    for col, val in (("empfaenger_name", body.empfaenger_name), ("steuerhinweis", body.steuerhinweis)):
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val.strip())
    for col, val in (
        ("empfaenger_anschrift", body.empfaenger_anschrift), ("empfaenger_email", body.empfaenger_email),
        ("einleitung", body.einleitung), ("notiz", body.notiz),
    ):
        if val is not None:
            fields.append(f"{col} = ?")
            values.append(val.strip() or None)
    fields.append("updated_at = datetime('now')")
    db.execute(f"UPDATE angebot SET {', '.join(fields)} WHERE id = ?", (*values, angebot_id))
    if body.positionen is not None:
        _pruefe_positionen(body.positionen)
        _positionen_schreiben(db, angebot_id, body.positionen)
    db.commit()
    return _row(db, angebot_id)


@router.delete("/{angebot_id}", status_code=204)
def loeschen(angebot_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("SELECT * FROM angebot WHERE id = ?", (angebot_id,)).fetchone()
    if cur is None:
        return
    check_gewerbe(db, user, cur["gewerbe_id"])
    if cur["status"] != "entwurf":
        raise HTTPException(400, "Nur Entwürfe lassen sich löschen — ein versendetes Angebot markierst du als abgelehnt.")
    db.execute("DELETE FROM angebot WHERE id = ?", (angebot_id,))
    db.commit()


class StatusIn(BaseModel):
    status: Literal["versendet", "angenommen", "abgelehnt"]
    datum: str | None = None

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


@router.post("/{angebot_id}/status")
def status_setzen(
    angebot_id: int, body: StatusIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    a = _check(db, user, angebot_id)
    heute = body.datum or dt.date.today().isoformat()
    if body.status == "versendet":
        if a["status"] != "entwurf":
            raise HTTPException(409, "Nur ein Entwurf lässt sich als versendet markieren.")
        db.execute("UPDATE angebot SET status = 'versendet', versendet_am = ?, updated_at = datetime('now') WHERE id = ?", (heute, angebot_id))
    else:
        if a["status"] == "entwurf":
            raise HTTPException(409, "Das Angebot ist noch ein Entwurf — erst senden oder als versendet markieren.")
        if body.status == "abgelehnt" and a["rechnung_id"] is not None:
            raise HTTPException(409, "Aus dem Angebot ist schon eine Rechnung entstanden.")
        db.execute("UPDATE angebot SET status = ?, antwort_am = ?, updated_at = datetime('now') WHERE id = ?", (body.status, heute, angebot_id))
    db.commit()
    return _row(db, angebot_id)


def _pdf(db: sqlite3.Connection, angebot_id: int) -> tuple[bytes, dict]:
    a = _row(db, angebot_id)
    g = db.execute("SELECT * FROM gewerbe WHERE id = ?", (a["gewerbe_id"],)).fetchone()
    return build_angebot_pdf(a, a["positionen"], g, entwurf=a["status"] == "entwurf"), a


@router.get("/{angebot_id}/pdf")
def pdf_ansehen(angebot_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _check(db, user, angebot_id)
    data, a = _pdf(db, angebot_id)
    return Response(
        content=data, media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="angebot-{a["nummer"]}.pdf"'},
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


@router.post("/{angebot_id}/senden")
def senden(
    angebot_id: int, body: SendenIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    _check(db, user, angebot_id)
    # Das gesendete PDF ist kein Entwurf mehr: erst den Status setzen, dann das PDF bauen
    a = db.execute("SELECT status FROM angebot WHERE id = ?", (angebot_id,)).fetchone()
    war_entwurf = a["status"] == "entwurf"
    if war_entwurf:
        db.execute(
            "UPDATE angebot SET status = 'versendet', versendet_am = ?, updated_at = datetime('now') WHERE id = ?",
            (dt.date.today().isoformat(), angebot_id),
        )
    data, row = _pdf(db, angebot_id)
    try:
        send_mail(
            db, absender_email=user["email"], absender_name=user.get("name"), an=str(body.an),
            betreff=body.betreff.strip(), text=body.text, anhang=(f"angebot-{row['nummer']}.pdf", data),
        )
    except (MailNotConfiguredError, MailSendError) as e:
        db.rollback()
        raise HTTPException(400, str(e))
    db.execute("UPDATE angebot SET empfaenger_email = COALESCE(empfaenger_email, ?) WHERE id = ?", (str(body.an), angebot_id))
    db.commit()
    return _row(db, angebot_id)


@router.post("/{angebot_id}/kopie", status_code=201)
def kopieren(angebot_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Neuer Entwurf mit denselben Inhalten (Datum heute, Gültigkeit +30 Tage)."""
    a = _row(db, _check(db, user, angebot_id)["id"])
    heute = dt.date.today().isoformat()
    aid = _neu(
        db, a["gewerbe_id"], heute, {**a, "gueltig_bis": add_days(heute, GUELTIG_TAGE)},
        [APositionIn(beschreibung=p["beschreibung"], menge=p["menge"], einzelpreis_cent=p["einzelpreis_cent"], art=p["art"]) for p in a["positionen"]],
    )
    db.commit()
    return _row(db, aid)


class InRechnungIn(BaseModel):
    optional_ids: list[int] = Field(default_factory=list)  # gewählte optionale Positionen
    datum: str | None = None  # Rechnungsdatum, leer = heute

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


@router.post("/{angebot_id}/rechnung", status_code=201)
def in_rechnung(
    angebot_id: int, body: InRechnungIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    """Rechnungsentwurf aus dem Angebot: normale Positionen + gewählte optionale; Angebot → angenommen."""
    a = _row(db, _check(db, user, angebot_id)["id"])
    if a["rechnung_id"] is not None:
        raise HTTPException(409, f"Aus diesem Angebot ist schon eine Rechnung entstanden ({a['rechnung']['nummer'] if a['rechnung'] else ''}).")
    if a["status"] not in ("versendet", "angenommen"):
        raise HTTPException(409, "Erst das Angebot versenden (oder als versendet markieren) — dann lässt es sich abrechnen.")
    optional = {p["id"] for p in a["positionen"] if p["art"] == "optional"}
    if set(body.optional_ids) - optional:
        raise HTTPException(400, "Unbekannte optionale Position gewählt.")
    positionen = [
        {"beschreibung": p["beschreibung"], "menge": p["menge"], "einzelpreis_cent": p["einzelpreis_cent"]}
        for p in a["positionen"]
        if p["art"] == "normal" or p["id"] in body.optional_ids
    ]
    datum = body.datum or dt.date.today().isoformat()
    rid = erstelle_rechnung(
        db,
        gewerbe_id=a["gewerbe_id"], datum=datum, leistungsdatum=None,
        empfaenger_name=a["empfaenger_name"], empfaenger_anschrift=a["empfaenger_anschrift"],
        empfaenger_email=a["empfaenger_email"],
        notiz=f"Bezug: Angebot {a['nummer']} vom {a['datum'][8:10]}.{a['datum'][5:7]}.{a['datum'][:4]}.",
        steuerhinweis=a["steuerhinweis"], positionen=positionen,
    )
    upsert_kontakt(db, a["gewerbe_id"], a["empfaenger_name"], a["empfaenger_anschrift"], a["empfaenger_email"])
    db.execute(
        "UPDATE angebot SET rechnung_id = ?, status = 'angenommen', "
        "antwort_am = COALESCE(antwort_am, ?), updated_at = datetime('now') WHERE id = ?",
        (rid, datum, angebot_id),
    )
    db.commit()
    rech = db.execute("SELECT id, nummer FROM rechnung WHERE id = ?", (rid,)).fetchone()
    return {"angebot": _row(db, angebot_id), "rechnung": dict(rech)}
