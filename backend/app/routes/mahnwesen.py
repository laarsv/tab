"""Mahnwesen: überfällige Rechnungen, Mahnung vorbereiten/erstellen (Stufen 1-3), PDF,
Mail-Versand, Basiszinssatz von der Bundesbank.

Aufbau wie Haben: Mahnwesen-Liste (überfällig, letzte Mahnung, nächste Stufe) →
Mahnungs-Seite mit Entwurf und Forderungsaufstellung → Mahnungen an der Rechnung.
Rechenregeln und Texte: services/mahnwesen.py. Erstellte Mahnungen sind unveränderlich;
eine falsche, noch nicht versendete lässt sich löschen und neu erstellen.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import sqlite3
import urllib.error
import urllib.request
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services.fristen import add_days
from ..services.mahnung_pdf import build_mahnung_pdf
from ..services.mahnwesen import (
    AUFSCHLAG_BP,
    PAUSCHALE_CENT,
    STUFEN,
    TEXTE,
    effektive_faelligkeit,
    mahnbetraege,
    mahnungen_zu,
    naechste_stufe,
    offen_cent,
    tage_ueberfaellig,
    ueberfaellige,
)
from ..services.mailer import MailNotConfiguredError, MailSendError, send_mail

router = APIRouter(prefix="/api/mahnwesen", tags=["mahnwesen"])

BUNDESBANK_URL = (
    "https://api.statistiken.bundesbank.de/rest/data/BBIN1/"
    "M.DE.BBK.BBKBAS2.EUR.ME?lastNObservations=1"
)
BASISZINS_GRENZEN_BP = (-1_000, 2_000)  # -10 % .. 20 % — außerhalb: unerwartetes Format


def _heute() -> str:
    return dt.date.today().isoformat()


class MahnungIn(BaseModel):
    rechnung_id: int
    stufe: int = Field(ge=1, le=3)
    frist_am: str
    gebuehr_cent: int = Field(default=0, ge=0, le=100_000)
    pauschale: bool = False
    # Verzugszinsen: Aufschlag auf den Basiszinssatz nach Kundenart, None = keine
    zinsen: Literal["geschaeftskunde", "verbraucher"] | None = None
    einleitung: str = Field(min_length=1, max_length=2000)
    schluss: str = Field(default="", max_length=2000)

    @field_validator("frist_am")
    @classmethod
    def _v_frist(cls, v: str) -> str:
        try:
            dt.date.fromisoformat(v)
        except ValueError:
            raise ValueError("frist_am muss im Format YYYY-MM-DD sein.")
        return v


def _rechnung(db: sqlite3.Connection, user: dict, rechnung_id: int):
    r = db.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Rechnung nicht gefunden.")
    return r, check_gewerbe(db, user, r["gewerbe_id"])


def _offene_rechnung(db: sqlite3.Connection, user: dict, rechnung_id: int, heute: str):
    """Rechnung + Gewerbe + effektive Fälligkeit; 400, wenn sie nicht gemahnt werden kann."""
    r, g = _rechnung(db, user, rechnung_id)
    if r["status"] != "versendet":
        raise HTTPException(400, "Gemahnt werden nur versendete, noch nicht bezahlte Rechnungen.")
    faellig = effektive_faelligkeit(r["datum"], r["faellig_am"])
    if faellig >= heute:
        raise HTTPException(400, "Die Rechnung ist noch nicht fällig.")
    if offen_cent(db, r) <= 0:
        raise HTTPException(400, "Für diese Rechnung ist nichts offen.")
    return r, g, faellig


def _baue(db: sqlite3.Connection, user: dict, body: MahnungIn):
    """Prüft die Eingaben und baut den Mahnung-Schnappschuss (Vorschau und Erstellen)."""
    heute = _heute()
    r, g, faellig = _offene_rechnung(db, user, body.rechnung_id, heute)
    if body.frist_am <= heute:
        raise HTTPException(400, "Die neue Zahlungsfrist muss in der Zukunft liegen.")
    mahnungen = mahnungen_zu(db, r["id"])
    erlaubt = naechste_stufe(mahnungen[0] if mahnungen else None)
    if body.stufe < erlaubt:
        raise HTTPException(
            400,
            f"Die Rechnung ist schon mit „{STUFEN[mahnungen[0]['stufe']]['label']}“ gemahnt. "
            f"Als Nächstes folgt „{STUFEN[erlaubt]['label']}“.",
        )
    satz = None
    if body.zinsen:
        if g["basiszinssatz_bp"] is None:
            raise HTTPException(
                400, "Für Verzugszinsen bitte zuerst den Basiszinssatz beim Gewerbe eintragen."
            )
        satz = g["basiszinssatz_bp"] + AUFSCHLAG_BP[body.zinsen]
    if body.pauschale and body.zinsen == "verbraucher":
        raise HTTPException(400, "Die Verzugspauschale gibt es nur gegenüber Geschäftskunden.")
    betraege = mahnbetraege(
        offen_cent=offen_cent(db, r),
        faellig=faellig,
        datum=heute,
        gebuehr_cent=body.gebuehr_cent,
        pauschale=body.pauschale,
        zinssatz_bp=satz,
    )
    mahnung = {
        "rechnung_id": r["id"],
        "stufe": body.stufe,
        "datum": heute,
        "frist_am": body.frist_am,
        **betraege,
        "einleitung": body.einleitung.strip(),
        "schluss": body.schluss.strip(),
        "gesendet_am": None,
    }
    return mahnung, r, g


def _check_mahnung(db: sqlite3.Connection, user: dict, mahnung_id: int):
    m = db.execute("SELECT * FROM mahnung WHERE id = ?", (mahnung_id,)).fetchone()
    if m is None:
        raise HTTPException(404, "Mahnung nicht gefunden.")
    r, g = _rechnung(db, user, m["rechnung_id"])
    return dict(m), r, g


# ── Liste + Entwurf ─────────────────────────────────────────────────────────

@router.get("/ueberfaellig")
def liste_ueberfaellig(
    gewerbe_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    heute = _heute()
    return {"heute": heute, "items": ueberfaellige(db, gewerbe_id, heute)}


@router.get("/entwurf/{rechnung_id}")
def entwurf(
    rechnung_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Vorschlag für die nächste Mahnung: Stufe, Frist, Gebühr und Texte (aus den Gewerbe-Einstellungen)."""
    heute = _heute()
    r, g, faellig = _offene_rechnung(db, user, rechnung_id, heute)
    mahnungen = mahnungen_zu(db, r["id"])
    stufe = naechste_stufe(mahnungen[0] if mahnungen else None)
    gebuehren = {1: g["mahn_gebuehr_1_cent"], 2: g["mahn_gebuehr_2_cent"], 3: g["mahn_gebuehr_3_cent"]}
    return {
        "rechnung": {
            "id": r["id"],
            "nummer": r["nummer"],
            "datum": r["datum"],
            "faellig_am": faellig,
            "empfaenger_name": r["empfaenger_name"],
            "offen_cent": offen_cent(db, r),
            "tage_ueberfaellig": tage_ueberfaellig(faellig, heute),
        },
        "stufe": stufe,
        "datum": heute,
        "frist_am": add_days(heute, g["mahn_frist_tage"]),
        "gebuehren_cent": gebuehren,
        "basiszinssatz_bp": g["basiszinssatz_bp"],
        "aufschlag_bp": AUFSCHLAG_BP,
        "pauschale_cent": PAUSCHALE_CENT,
        "stufen": {k: v["label"] for k, v in STUFEN.items()},
        "texte": TEXTE,
    }


@router.post("/vorschau")
def vorschau(
    body: MahnungIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Entwurfs-PDF („ENTWURF“ über der Seite) mit denselben Prüfungen und Beträgen wie beim
    Erstellen — speichert nichts."""
    mahnung, r, g = _baue(db, user, body)
    pdf = build_mahnung_pdf(mahnung, r, g, entwurf=True)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="mahnung-entwurf.pdf"'},
    )


@router.post("", status_code=201)
def erstellen(
    body: MahnungIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    mahnung, _r, _g = _baue(db, user, body)
    cur = db.execute(
        """
        INSERT INTO mahnung (rechnung_id, stufe, datum, frist_am, offen_cent, gebuehr_cent,
                             pauschale_cent, zinsen_cent, zinssatz_bp, zinstage, gesamt_cent,
                             einleitung, schluss)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            mahnung["rechnung_id"], mahnung["stufe"], mahnung["datum"], mahnung["frist_am"],
            mahnung["offen_cent"], mahnung["gebuehr_cent"], mahnung["pauschale_cent"],
            mahnung["zinsen_cent"], mahnung["zinssatz_bp"], mahnung["zinstage"],
            mahnung["gesamt_cent"], mahnung["einleitung"], mahnung["schluss"] or None,
        ),
    )
    db.commit()
    return dict(db.execute("SELECT * FROM mahnung WHERE id = ?", (cur.lastrowid,)).fetchone())


# ── Einzelne Mahnung: PDF, Mail, Löschen ────────────────────────────────────

def _pdf(m: dict, r, g) -> bytes:
    return build_mahnung_pdf(m, r, g)


def _dateiname(m: dict, r) -> str:
    return f"mahnung-{r['nummer']}-stufe{m['stufe']}.pdf"


@router.get("/{mahnung_id}/pdf")
def mahnung_pdf(
    mahnung_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    m, r, g = _check_mahnung(db, user, mahnung_id)
    return Response(
        content=_pdf(m, r, g),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{_dateiname(m, r)}"'},
    )


class MahnungSendenIn(BaseModel):
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


@router.post("/{mahnung_id}/senden")
def mahnung_senden(
    mahnung_id: int,
    body: MahnungSendenIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    m, r, g = _check_mahnung(db, user, mahnung_id)
    try:
        send_mail(
            db,
            absender_email=user["email"],
            absender_name=user.get("name"),
            an=str(body.an),
            betreff=body.betreff.strip(),
            text=body.text,
            anhang=(_dateiname(m, r), _pdf(m, r, g)),
        )
    except (MailNotConfiguredError, MailSendError) as e:
        raise HTTPException(400, str(e))
    db.execute("UPDATE mahnung SET gesendet_am = ? WHERE id = ?", (_heute(), mahnung_id))
    db.commit()
    return dict(db.execute("SELECT * FROM mahnung WHERE id = ?", (mahnung_id,)).fetchone())


@router.delete("/{mahnung_id}", status_code=204)
def mahnung_loeschen(
    mahnung_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    m, _r, _g = _check_mahnung(db, user, mahnung_id)
    if m["gesendet_am"]:
        raise HTTPException(
            400, "Versendete Mahnungen bleiben stehen — erstelle bei Bedarf eine neue."
        )
    db.execute("DELETE FROM mahnung WHERE id = ?", (mahnung_id,))
    db.commit()


# ── Basiszinssatz (Bundesbank) ──────────────────────────────────────────────

def _letzter_stichtag(iso: str) -> str:
    """Monat (JJJJ-MM) der letzten Änderung des Basiszinssatzes: 1. Januar oder 1. Juli (§ 247 BGB)."""
    return f"{iso[:4]}-{'07' if int(iso[5:7]) >= 7 else '01'}"


@router.get("/basiszinssatz", dependencies=[Depends(get_current_user)])
def basiszinssatz_bundesbank():
    """Aktuellen Basiszinssatz bei der Bundesbank abfragen (SDMX-CSV). Speichert nichts —
    der Wert wird mit den Gewerbe-Einstellungen übernommen."""
    req = urllib.request.Request(BUNDESBANK_URL, headers={"Accept": "text/csv"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8-sig", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        raise HTTPException(502, "Die Bundesbank ist gerade nicht erreichbar — bitte von Hand eintragen.")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    if not rows or "TIME_PERIOD" not in rows[0] or "OBS_VALUE" not in rows[0]:
        raise HTTPException(502, "Unerwartete Antwort der Bundesbank — bitte von Hand eintragen.")
    kopf = rows[0]
    best = None
    for zeile in rows[1:]:
        try:
            monat = zeile[kopf.index("TIME_PERIOD")]
            bp = round(float(zeile[kopf.index("OBS_VALUE")].strip()) * 100)
        except (IndexError, ValueError):
            continue
        if len(monat) == 7 and BASISZINS_GRENZEN_BP[0] <= bp <= BASISZINS_GRENZEN_BP[1]:
            if best is None or monat > best[0]:
                best = (monat, bp)
    if best is None:
        raise HTTPException(502, "Kein Wert in der Antwort der Bundesbank — bitte von Hand eintragen.")
    monat, bp = best
    # Im Januar/Juli steht der neue Satz oft noch nicht in der Reihe: dann ist der Wert alt.
    aktuell = _letzter_stichtag(f"{monat}-01") == _letzter_stichtag(_heute())
    return {"basiszinssatz_bp": bp, "monat": monat, "aktuell": aktuell}
