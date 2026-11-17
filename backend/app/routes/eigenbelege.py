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
    daten = eb.pdf(angaben, gewerbe)
    try:
        beleg_id = speichere_beleg(
            db,
            gewerbe_id=body.gewerbe_id,
            original_name=f"Eigenbeleg {angaben['nummer']}.pdf",
            data=daten,
            content_type="application/pdf",
            buchung_id=body.buchung_id,
        )
    except BelegAbgelehnt as e:
        raise HTTPException(400, str(e))
    db.execute("UPDATE beleg SET eigenbeleg = ? WHERE id = ?",
               (json.dumps(angaben, ensure_ascii=False, sort_keys=True), beleg_id))
    db.commit()
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
        "hinweise": eb.hinweise(db, body.gewerbe_id, datum=angaben["datum"], betrag_cent=body.betrag_cent,
                                buchung_id=body.buchung_id),
    }
