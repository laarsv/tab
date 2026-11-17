"""Digitale Eigenbelege (v42, services/eigenbeleg.py): Angaben → PDF → normaler Beleg (Eingang oder an der
Buchung). Eigene Datei, damit routes/belege.py schlank bleibt. Nur der Inhaber (Steuerberatung: nur lesen)."""
from __future__ import annotations

import datetime as dt
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth.deps import check_gewerbe, get_current_user, nur_inhaber
from ..db import get_db
from ..services import eigenbeleg as eb
from ..services.abschluss import _datei_sha256
from ..services.beleg_store import BelegAbgelehnt, speichere_beleg

router = APIRouter(prefix="/api/eigenbelege", tags=["eigenbelege"], dependencies=[Depends(get_current_user)])


class EigenbelegIn(BaseModel):
    gewerbe_id: int
    buchung_id: int | None = None
    datum: str
    betrag_cent: int = Field(gt=0, le=100_000_000)
    empfaenger: str = Field(min_length=1, max_length=200)
    gegenstand: str = Field(min_length=1, max_length=500)
    anlass: str = Field(min_length=1, max_length=500)
    zahlungsart: str | None = None
    grund: str
    grund_text: str | None = Field(None, max_length=500)
    bestaetigt: bool = False


class BewirtungIn(BaseModel):
    gewerbe_id: int
    buchung_id: int | None = None
    rechnung_beleg_ids: list[int] = Field(default_factory=list, max_length=10)
    datum: str
    ort: str | None = Field(None, max_length=200)
    anlass: str = Field(min_length=1, max_length=500)
    teilnehmer: str = Field(min_length=1, max_length=2000)
    betrag_cent: int | None = Field(None, gt=0, le=100_000_000)
    trinkgeld_cent: int | None = Field(None, ge=0, le=100_000_000)
    bestaetigt: bool = False


class BewirtungPruefenIn(BaseModel):
    gewerbe_id: int
    buchung_id: int | None = None
    rechnung_beleg_ids: list[int] = Field(default_factory=list, max_length=10)
    datum: str | None = None
    betrag_cent: int | None = None
    trinkgeld_cent: int | None = None


class PruefenIn(BaseModel):
    gewerbe_id: int
    buchung_id: int | None = None
    datum: str | None = None
    betrag_cent: int | None = None
    kategorie_key: str | None = None


def _buchung(db: sqlite3.Connection, gewerbe_id: int, buchung_id: int | None):
    if buchung_id is None:
        return None
    b = db.execute("SELECT * FROM buchung WHERE id = ?", (buchung_id,)).fetchone()
    if b is None:
        raise HTTPException(404, "Buchung nicht gefunden.")
    if b["gewerbe_id"] != gewerbe_id:
        raise HTTPException(400, "Buchung gehört zu einem anderen Gewerbe.")
    typen = {r[0] for r in db.execute(
        "SELECT k.typ FROM buchung_position p JOIN kategorie k ON k.id = p.kategorie_id WHERE p.buchung_id = ?",
        (buchung_id,),
    )}
    if typen and "ausgabe" not in typen:
        raise HTTPException(400, "Eigenbelege gibt es nur für Ausgaben.")
    return b


def _rechnungen(db: sqlite3.Connection, gewerbe_id: int, buchung_id: int | None, ids: list[int]) -> list[sqlite3.Row]:
    """Die Rechnung(en), auf die der Bewirtungsbeleg verweist: ausdrücklich genannte Belege, sonst die an der
    Buchung hängenden (ohne Eigen-/Bewirtungsbelege)."""
    if ids:
        rows = []
        for i in dict.fromkeys(ids):
            r = db.execute("SELECT * FROM beleg WHERE id = ?", (i,)).fetchone()
            if r is None or r["gewerbe_id"] != gewerbe_id:
                raise HTTPException(404, "Rechnungsbeleg nicht gefunden.")
            if r["eigenbeleg"]:
                raise HTTPException(400, "Ein Eigen- oder Bewirtungsbeleg ist keine Restaurantrechnung.")
            rows.append(r)
        return rows
    if buchung_id is None:
        return []
    return db.execute(
        "SELECT * FROM beleg WHERE buchung_id = ? AND eigenbeleg IS NULL ORDER BY id", (buchung_id,)
    ).fetchall()


def _antwort(db: sqlite3.Connection, beleg_id: int, angaben: dict, hinweise: list[dict]) -> dict:
    r = db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone()
    return {
        "id": r["id"],
        "gewerbe_id": r["gewerbe_id"],
        "buchung_id": r["buchung_id"],
        "original_name": r["original_name"],
        "content_type": r["content_type"],
        "size_bytes": r["size_bytes"],
        "created_at": r["created_at"],
        "faellig_am": r["faellig_am"],
        "offen": r["buchung_id"] is None,
        "eigenbeleg": angaben,
        "hinweise": hinweise,
    }


def _speichern(db: sqlite3.Connection, gewerbe_id: int, buchung_id: int | None, name: str, daten: bytes,
               angaben: dict) -> int:
    try:
        beleg_id = speichere_beleg(db, gewerbe_id=gewerbe_id, original_name=name, data=daten,
                                   content_type="application/pdf", buchung_id=buchung_id)
    except BelegAbgelehnt as e:
        raise HTTPException(400, str(e))
    db.execute("UPDATE beleg SET eigenbeleg = ? WHERE id = ?",
               (json.dumps(angaben, ensure_ascii=False, sort_keys=True), beleg_id))
    db.commit()
    return beleg_id


@router.post("/bewirtung/pruefen")
def bewirtung_pruefen(body: BewirtungPruefenIn, user: dict = Depends(nur_inhaber),
                      db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    _buchung(db, body.gewerbe_id, body.buchung_id)
    rechnungen = _rechnungen(db, body.gewerbe_id, body.buchung_id, body.rechnung_beleg_ids)
    return {"hinweise": eb.bewirtung_hinweise(datum=body.datum, betrag_cent=body.betrag_cent,
                                              trinkgeld_cent=body.trinkgeld_cent, rechnungen=len(rechnungen))}


@router.post("/bewirtung", status_code=201)
def bewirtung_erstellen(body: BewirtungIn, user: dict = Depends(nur_inhaber),
                        db: sqlite3.Connection = Depends(get_db)):
    """Bewirtungsbeleg: Anlass + Teilnehmer (+ Ort, Höhe) mit elektronischer Freigabe, als PDF mit Verweis auf
    die Restaurantrechnung (BMF 19.11.2025, Rn. 19–22)."""
    gewerbe = check_gewerbe(db, user, body.gewerbe_id)
    _buchung(db, body.gewerbe_id, body.buchung_id)
    try:
        datum = dt.date.fromisoformat(body.datum)
    except ValueError:
        raise HTTPException(400, "Datum muss im Format JJJJ-MM-TT sein.")
    if datum > dt.date.today():
        raise HTTPException(400, "Der Tag der Bewirtung liegt in der Zukunft.")
    if not body.bestaetigt:
        raise HTTPException(400, "Bitte die Angaben bestätigen — das ist die elektronische Freigabe.")
    anlass, teilnehmer = body.anlass.strip(), body.teilnehmer.strip()
    if not anlass or not teilnehmer:
        raise HTTPException(400, "Anlass und Teilnehmer sind Pflicht.")
    if body.trinkgeld_cent and body.betrag_cent and body.trinkgeld_cent > body.betrag_cent:
        raise HTTPException(400, "Das Trinkgeld ist höher als der Gesamtbetrag.")
    rechnungen = _rechnungen(db, body.gewerbe_id, body.buchung_id, body.rechnung_beleg_ids)
    angaben = {
        "art": "bewirtung",
        "nummer": eb.naechste_nummer(db, body.gewerbe_id, datum.year, "BW"),
        "datum": datum.isoformat(),
        "ort": (body.ort or "").strip() or None,
        "anlass": anlass,
        "teilnehmer": teilnehmer,
        "betrag_cent": body.betrag_cent,
        "trinkgeld_cent": body.trinkgeld_cent or None,
        "rechnungen": [{"id": r["id"], "name": r["original_name"], "sha256": _datei_sha256(r["stored_name"])}
                       for r in rechnungen],
        "erstellt_am": eb.jetzt(),
        "erstellt_von": user["email"],
    }
    angaben["pruefwert"] = eb.angaben_hash(angaben)
    beleg_id = _speichern(db, body.gewerbe_id, body.buchung_id, f"Bewirtungsbeleg {angaben['nummer']}.pdf",
                          eb.bewirtung_pdf(angaben, gewerbe), angaben)
    return _antwort(db, beleg_id, angaben, eb.bewirtung_hinweise(
        datum=angaben["datum"], betrag_cent=body.betrag_cent, trinkgeld_cent=body.trinkgeld_cent,
        rechnungen=len(rechnungen)))


@router.get("/optionen")
def optionen():
    return {
        "gruende": [{"value": k, "label": v} for k, v in eb.GRUENDE.items()],
        "zahlungsarten": [{"value": k, "label": v} for k, v in eb.ZAHLUNGSARTEN.items()],
        "hoher_betrag_cent": eb.HOHER_BETRAG_CENT,
    }


@router.post("/pruefen")
def pruefen(body: PruefenIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    _buchung(db, body.gewerbe_id, body.buchung_id)
    return {"hinweise": eb.hinweise(db, body.gewerbe_id, datum=body.datum, betrag_cent=body.betrag_cent,
                                    buchung_id=body.buchung_id, kategorie_key=body.kategorie_key)}


@router.post("", status_code=201)
def erstellen(body: EigenbelegIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    gewerbe = check_gewerbe(db, user, body.gewerbe_id)
    _buchung(db, body.gewerbe_id, body.buchung_id)
    try:
        datum = dt.date.fromisoformat(body.datum)
    except ValueError:
        raise HTTPException(400, "Datum muss im Format JJJJ-MM-TT sein.")
    if datum > dt.date.today():
        raise HTTPException(400, "Das Datum der Ausgabe liegt in der Zukunft.")
    if body.grund not in eb.GRUENDE:
        raise HTTPException(400, "Bitte angeben, warum kein Originalbeleg vorliegt.")
    grund_text = (body.grund_text or "").strip()
    if body.grund == "sonstiges" and not grund_text:
        raise HTTPException(400, "Bei „Sonstiger Grund“ bitte kurz erklären, warum der Beleg fehlt.")
    if body.zahlungsart and body.zahlungsart not in eb.ZAHLUNGSARTEN:
        raise HTTPException(400, "Unbekannte Zahlungsart.")
    if not body.bestaetigt:
        raise HTTPException(400, "Bitte die Erklärung bestätigen — das ist die elektronische Freigabe.")
    texte = {k: getattr(body, k).strip() for k in ("empfaenger", "gegenstand", "anlass")}
    if not all(texte.values()):
        raise HTTPException(400, "Zahlungsempfänger, Gegenstand und Anlass sind Pflicht.")

    angaben = {
        "art": "eigenbeleg",
        "nummer": eb.naechste_nummer(db, body.gewerbe_id, datum.year),
        "datum": datum.isoformat(),
        "betrag_cent": body.betrag_cent,
        **texte,
        "zahlungsart": body.zahlungsart or None,
        "grund": body.grund,
        "grund_text": grund_text or None,
        "erstellt_am": eb.jetzt(),
        "erstellt_von": user["email"],
    }
    angaben["pruefwert"] = eb.angaben_hash(angaben)
    beleg_id = _speichern(db, body.gewerbe_id, body.buchung_id, f"Eigenbeleg {angaben['nummer']}.pdf",
                          eb.pdf(angaben, gewerbe), angaben)
    return _antwort(db, beleg_id, angaben, eb.hinweise(db, body.gewerbe_id, datum=angaben["datum"],
                                                       betrag_cent=body.betrag_cent, buchung_id=body.buchung_id))
