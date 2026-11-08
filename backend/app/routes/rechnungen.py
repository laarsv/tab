"""Rechnungen (Kleinunternehmer, §19-Hinweis): CRUD, PDF, Mail-Versand, Status.

Nummer: fortlaufend je Gewerbe + Jahr ({jahr}-{lauf:04d}), vergeben beim Anlegen.
Löschen nur für die höchste Nummer eines Jahres (keine Lücken) und nicht nach
Versand/Bezahlung — sonst stornieren. Inhalt editierbar nur im Status 'entwurf'.
"""
from __future__ import annotations

import datetime as dt
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services.e_rechnung import rechnungs_pdf
from ..services import zahlungen as zsvc
from ..services.mailer import MailNotConfiguredError, MailSendError, send_mail
from ..services.fristen import faelligkeit
from ..services.mahnwesen import effektive_faelligkeit, mahnungen_zu, tage_ueberfaellig
from ..services.rechnung_pdf import STEUERHINWEISE
from ..services.rechnungen import erstelle_rechnung, standard_zahlungsziel
from .kontakte import upsert_kontakt


def _skonto_felder(prozent: float | None, tage: int | None, ziel: int | None) -> tuple[int | None, int | None]:
    """Skonto prüfen → (Basispunkte, Tage). Beides oder nichts; die Frist reicht nicht über das Zahlungsziel."""
    if prozent is None and tage is None:
        return None, None
    if prozent is None or tage is None:
        raise HTTPException(400, "Skonto braucht einen Prozentsatz und eine Frist in Tagen.")
    bp = round(prozent * 100)
    if not 10 <= bp <= 1000:
        raise HTTPException(400, "Das Skonto muss zwischen 0,1 und 10 % liegen.")
    if ziel is not None and tage > ziel:
        raise HTTPException(400, "Die Skonto-Frist darf nicht länger sein als das Zahlungsziel.")
    return bp, tage

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
    zahlungsziel_tage: int | None = Field(default=None, ge=0, le=120)  # None = Standard des Gewerbes
    skonto_prozent: float | None = Field(default=None, gt=0, le=10)    # Skonto bei früher Zahlung
    skonto_tage: int | None = Field(default=None, ge=1, le=120)
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
    zahlungsziel_tage: int | None = Field(default=None, ge=0, le=120)
    skonto_prozent: float | None = Field(default=None, gt=0, le=10)  # explizit null = Skonto entfernen
    skonto_tage: int | None = Field(default=None, ge=1, le=120)
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


def _check_rechnung(db: sqlite3.Connection, user: dict, rechnung_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    return row


def _row(db: sqlite3.Connection, rechnung_id: int) -> dict:
    r = db.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")
    d = dict(r)
    d["positionen"] = _positionen(db, rechnung_id)
    d["summe_cent"] = sum(round(p["menge"] * p["einzelpreis_cent"]) for p in d["positionen"])
    d["mahnungen"] = mahnungen_zu(db, rechnung_id)
    # Zahlungsstand (Teilzahlungen, Skonto, Ausbuchungen) und Skonto-Angebot
    st = zsvc.stand(db, d)
    d.update(
        bezahlt_cent=st["bezahlt_cent"], ausgebucht_cent=st["ausgebucht_cent"], offen_cent=st["offen_cent"],
        gebucht_cent=st["gebucht_cent"], ungebucht_cent=st["ungebucht_cent"], zahlungen=st["zahlungen"],
    )
    d["skonto_prozent"] = d["skonto_bp"] / 100 if d["skonto_bp"] else None
    d["skonto_cent"] = zsvc.skonto_cent(d["summe_cent"], d["skonto_bp"])
    d["skonto_bis"] = zsvc.skonto_bis(d["datum"], d["skonto_tage"]) if d["skonto_bp"] else None
    # Überfällig nur bei versendeten, noch nicht bezahlten Rechnungen (ohne Ziel: Datum + 30 Tage).
    d["ueberfaellig_tage"] = 0
    if d["status"] == "versendet":
        faellig = effektive_faelligkeit(d["datum"], d["faellig_am"])
        d["ueberfaellig_tage"] = tage_ueberfaellig(faellig, dt.date.today().isoformat())
    return d


@router.get("")
def list_rechnungen(
    gewerbe_id: int,
    jahr: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    ids = [
        r["id"]
        for r in db.execute(
            "SELECT id FROM rechnung WHERE gewerbe_id = ? AND jahr = ? "
            "ORDER BY laufnummer DESC",
            (gewerbe_id, jahr),
        )
    ]
    return [_row(db, i) for i in ids]


@router.post("/vorschau")
def rechnung_vorschau(
    body: RechnungIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """PDF-Vorschau aus ungespeicherten Formulardaten — legt NICHTS an und
    verbraucht keine Nummer (zeigt die voraussichtliche)."""
    g = check_gewerbe(db, user, body.gewerbe_id)
    jahr = int(body.datum[:4])
    lauf = (
        db.execute(
            "SELECT COALESCE(MAX(laufnummer), 0) FROM rechnung WHERE gewerbe_id = ? AND jahr = ?",
            (body.gewerbe_id, jahr),
        ).fetchone()[0]
        + 1
    )
    ziel = (
        body.zahlungsziel_tage
        if body.zahlungsziel_tage is not None
        else standard_zahlungsziel(db, body.gewerbe_id)
    )
    skonto_bp, skonto_tage = _skonto_felder(body.skonto_prozent, body.skonto_tage, ziel)
    rechnung = {
        "nummer": f"{jahr}-{lauf:04d}",
        "datum": body.datum,
        "faellig_am": faelligkeit(body.datum, ziel),
        "skonto_bp": skonto_bp,
        "skonto_tage": skonto_tage,
        "leistungsdatum": (body.leistungsdatum or "").strip() or None,
        "empfaenger_name": body.empfaenger_name.strip(),
        "empfaenger_anschrift": (body.empfaenger_anschrift or "").strip() or None,
        "notiz": (body.notiz or "").strip() or None,
        "steuerhinweis": body.steuerhinweis,
    }
    pdf = rechnungs_pdf(rechnung, [p.model_dump() for p in body.positionen], g)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="rechnung-vorschau.pdf"'},
    )


@router.post("", status_code=201)
def create_rechnung(
    body: RechnungIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, body.gewerbe_id)
    ziel = body.zahlungsziel_tage if body.zahlungsziel_tage is not None else standard_zahlungsziel(db, body.gewerbe_id)
    skonto_bp, skonto_tage = _skonto_felder(body.skonto_prozent, body.skonto_tage, ziel)
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
        zahlungsziel_tage=body.zahlungsziel_tage,
        skonto_bp=skonto_bp,
        skonto_tage=skonto_tage,
    )
    # Empfänger automatisch als Kontakt merken (füllt den Kontakte-Speicher von selbst).
    upsert_kontakt(db, body.gewerbe_id, body.empfaenger_name,
                   body.empfaenger_anschrift, body.empfaenger_email)
    db.commit()
    return _row(db, rid)


@router.patch("/{rechnung_id}")
def update_rechnung(
    rechnung_id: int,
    body: RechnungPatch,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = _check_rechnung(db, user, rechnung_id)

    inhalt_geaendert = any(
        v is not None
        for v in (body.datum, body.leistungsdatum, body.empfaenger_name,
                  body.empfaenger_anschrift, body.steuerhinweis, body.positionen,
                  body.zahlungsziel_tage)
    ) or bool({"skonto_prozent", "skonto_tage"} & body.model_fields_set)
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
    if body.datum is not None or body.zahlungsziel_tage is not None:
        # Fälligkeit neu rechnen (nur Entwürfe, siehe oben). Ohne eigenes Ziel: das bisherige,
        # bei Bestand ohne Ziel das Standard-Zahlungsziel des Gewerbes.
        ziel = body.zahlungsziel_tage
        if ziel is None:
            ziel = cur["zahlungsziel_tage"]
        if ziel is None:
            ziel = standard_zahlungsziel(db, cur["gewerbe_id"])
        fields += ["zahlungsziel_tage = ?", "faellig_am = ?"]
        values += [ziel, faelligkeit(body.datum or cur["datum"], ziel)]
    # Skonto: gesetzte Felder übernehmen, sonst das bisherige; dann gemeinsam gegen das Ziel prüfen
    if {"skonto_prozent", "skonto_tage", "zahlungsziel_tage", "datum"} & body.model_fields_set:
        prozent = body.skonto_prozent if "skonto_prozent" in body.model_fields_set else (
            cur["skonto_bp"] / 100 if cur["skonto_bp"] else None)
        tage = body.skonto_tage if "skonto_tage" in body.model_fields_set else cur["skonto_tage"]
        ziel_neu = body.zahlungsziel_tage if body.zahlungsziel_tage is not None else (
            cur["zahlungsziel_tage"] if cur["zahlungsziel_tage"] is not None else standard_zahlungsziel(db, cur["gewerbe_id"]))
        bp, t = _skonto_felder(prozent, tage, ziel_neu)
        fields += ["skonto_bp = ?", "skonto_tage = ?"]
        values += [bp, t]
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


@router.delete("/{rechnung_id}", status_code=204)
def delete_rechnung(
    rechnung_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    cur = db.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if cur is None:
        return
    check_gewerbe(db, user, cur["gewerbe_id"])
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


@router.post("/{rechnung_id}/status")
def set_status(
    rechnung_id: int,
    body: StatusIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    if body.status not in ("entwurf", "versendet", "bezahlt", "storniert"):
        raise HTTPException(400, "Unbekannter Status.")
    cur = _check_rechnung(db, user, rechnung_id)
    heute = dt.date.today().isoformat()
    if body.status in ("entwurf", "versendet") and cur["status"] == "bezahlt" and zsvc.zahlungen_zu(db, rechnung_id):
        raise HTTPException(409, "Die Rechnung hat Zahlungen — lösche sie zuerst, um die Rechnung wieder zu öffnen.")
    if body.status == "bezahlt":
        # „Als bezahlt markieren“: der offene Rest gilt als am Datum gezahlt (ohne Buchung — die folgt
        # über „Als Einnahme buchen“ an der Zahlung)
        rest = zsvc.offen_cent(db, cur) if cur["status"] in ("entwurf", "versendet") else 0
        if rest > 0:
            zsvc.zahlung_anlegen(db, rechnung=cur, datum=body.datum or heute, betrag_cent=rest)
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


class ZahlungIn(BaseModel):
    datum: str
    betrag_cent: int = Field(gt=0)
    buchen: bool = True  # gleich die Einnahme-Buchung anlegen (Kategorie nach Steuerhinweis)
    rest_ausbuchen: Literal["skonto", "ausfall"] | None = None  # Rest nach Teilzahlung ausbuchen
    notiz: str | None = Field(default=None, max_length=200)

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str) -> str:
        return _valid_date(v)


@router.post("/{rechnung_id}/zahlungen", status_code=201)
def zahlung_erfassen(
    rechnung_id: int,
    body: ZahlungIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Zahlung auf eine versendete Rechnung: Teilzahlung oder Rest, optional mit Einnahme-Buchung und
    Ausbuchen des Rests (Skonto bzw. Forderungsausfall). Bezahlt ist die Rechnung, wenn nichts mehr offen ist."""
    r = _check_rechnung(db, user, rechnung_id)
    if r["status"] != "versendet":
        raise HTTPException(409, "Zahlungen lassen sich nur auf versendete, noch nicht bezahlte Rechnungen erfassen.")
    if body.datum < r["datum"]:
        raise HTTPException(400, "Das Zahlungsdatum liegt vor dem Rechnungsdatum.")
    if body.datum > dt.date.today().isoformat():
        raise HTTPException(400, "Das Zahlungsdatum liegt in der Zukunft.")
    offen = zsvc.offen_cent(db, r)
    if body.betrag_cent > offen:
        raise HTTPException(400, f"Der Betrag ist höher als der offene Betrag ({offen // 100},{offen % 100:02d} €).")
    rest = offen - body.betrag_cent
    if body.rest_ausbuchen and rest <= 0:
        raise HTTPException(400, "Es bleibt kein Rest zum Ausbuchen.")
    buchung_id = (
        zsvc.einnahme_buchen(db, r, body.datum, body.betrag_cent, teilzahlung=rest > 0 and not body.rest_ausbuchen)
        if body.buchen else None
    )
    zsvc.zahlung_anlegen(db, rechnung=r, datum=body.datum, betrag_cent=body.betrag_cent, buchung_id=buchung_id, notiz=body.notiz)
    if body.rest_ausbuchen:
        zsvc.zahlung_anlegen(db, rechnung=r, datum=body.datum, betrag_cent=rest, art=body.rest_ausbuchen)
    zsvc.aktualisiere_status(db, rechnung_id)
    db.commit()
    return _row(db, rechnung_id)


@router.delete("/{rechnung_id}/zahlungen/{zahlung_id}")
def zahlung_loeschen(
    rechnung_id: int,
    zahlung_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _check_rechnung(db, user, rechnung_id)
    z = db.execute(
        "SELECT * FROM rechnung_zahlung WHERE id = ? AND rechnung_id = ?", (zahlung_id, rechnung_id)
    ).fetchone()
    if z is None:
        raise HTTPException(404, "Zahlung nicht gefunden.")
    if z["buchung_id"] is not None:
        raise HTTPException(409, "Diese Zahlung ist als Einnahme gebucht — lösche zuerst die Buchung.")
    db.execute("DELETE FROM rechnung_zahlung WHERE id = ?", (zahlung_id,))
    zsvc.aktualisiere_status(db, rechnung_id)
    db.commit()
    return _row(db, rechnung_id)


def _pdf_bytes(db: sqlite3.Connection, rechnung_id: int) -> tuple[bytes, dict]:
    r = _row(db, rechnung_id)
    g = db.execute("SELECT * FROM gewerbe WHERE id = ?", (r["gewerbe_id"],)).fetchone()
    return rechnungs_pdf(r, r["positionen"], g), r


@router.get("/{rechnung_id}/pdf")
def rechnung_pdf(
    rechnung_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _check_rechnung(db, user, rechnung_id)
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
    _check_rechnung(db, user, rechnung_id)
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
