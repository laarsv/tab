"""Fristen-Seite: Steuerfristen (services/steuerfristen.py), Erledigt-Markierung, Einstellung
und Kalender-Abo (iCal-Feed mit geheimem Link).

Der Feed-Link ist ein Zufalls-Token in der URL; gespeichert wird nur sein SHA-256-Hash, der Link
selbst nur beim Erzeugen angezeigt. Wer den Link kennt, sieht die Fristen — sonst nichts.
Ein neuer Link macht den alten ungültig. Der Feed-Endpunkt ist ohne Login erreichbar (Kalender-
Apps schicken keinen Cookie) und liefert ausschließlich die Fristen des Link-Besitzers.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import logging
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field

from ..auth.deps import get_current_user, ist_admin
from ..db import get_db
from ..services.steuerfristen import (
    BALD_TAGE,
    dringend_anzahl,
    kalender_ics,
    steuerfristen,
    vz_faellig,
)

router = APIRouter(prefix="/api/fristen", tags=["fristen"])


def _heute() -> str:
    return dt.date.today().isoformat()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _gewerbe(db: sqlite3.Connection, email: str) -> list[sqlite3.Row]:
    """Aktive Gewerbe des Nutzers — dieselbe Sichtbarkeit wie die Gewerbe-Liste (Admins sehen
    zusätzlich den herrenlosen Alt-Bestand)."""
    sichtbar = "(owner_email = ? OR owner_email IS NULL)" if ist_admin({"email": email}) else "owner_email = ?"
    return db.execute(
        f"SELECT id, name, ustva_zeitraum, ustva_dauerfrist FROM gewerbe WHERE {sichtbar} AND aktiv = 1 ORDER BY name COLLATE NOCASE",
        (email,),
    ).fetchall()


def _einstellung(db: sqlite3.Connection, email: str) -> dict:
    r = db.execute("SELECT * FROM frist_einstellung WHERE email = ?", (email,)).fetchone()
    return {
        "est_vorauszahlung": bool(r["est_vorauszahlung"]) if r else False,
        "kalender_aktiv": bool(r and r["kalender_token_hash"]),
        "kalender_seit": r["kalender_seit"] if r else None,
    }


def _fristen(db: sqlite3.Connection, email: str) -> list[dict]:
    return steuerfristen(
        db,
        email=email,
        gewerbe=_gewerbe(db, email),
        heute=_heute(),
        est_vorauszahlung=_einstellung(db, email)["est_vorauszahlung"],
    )


fristen_des_nutzers = _fristen  # für die Übersicht


@router.get("")
def liste(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    items = _fristen(db, user["email"])
    return {
        "heute": _heute(),
        "bald_tage": BALD_TAGE,
        "items": items,
        "dringend": dringend_anzahl(items),
        "einstellung": _einstellung(db, user["email"]),
    }


class ErledigtIn(BaseModel):
    schluessel: str
    erledigt: bool


@router.post("/erledigt")
def erledigt_setzen(
    body: ErledigtIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    frist = next((f for f in _fristen(db, user["email"]) if f["schluessel"] == body.schluessel), None)
    if frist is None or not frist["erledigbar"]:
        raise HTTPException(404, "Diese Frist gibt es nicht oder sie lässt sich nicht abhaken.")
    if body.erledigt:
        db.execute(
            "INSERT INTO frist_erledigt (email, schluessel, erledigt_am) VALUES (?, ?, ?) "
            "ON CONFLICT(email, schluessel) DO UPDATE SET erledigt_am = excluded.erledigt_am",
            (user["email"], body.schluessel, _heute()),
        )
    else:
        db.execute(
            "DELETE FROM frist_erledigt WHERE email = ? AND schluessel = ?",
            (user["email"], body.schluessel),
        )
    db.commit()
    return {"ok": True}


class EinstellungIn(BaseModel):
    est_vorauszahlung: bool


@router.put("/einstellung")
def einstellung_setzen(
    body: EinstellungIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    db.execute(
        "INSERT INTO frist_einstellung (email, est_vorauszahlung) VALUES (?, ?) "
        "ON CONFLICT(email) DO UPDATE SET est_vorauszahlung = excluded.est_vorauszahlung, "
        "updated_at = datetime('now')",
        (user["email"], 1 if body.est_vorauszahlung else 0),
    )
    db.commit()
    return _einstellung(db, user["email"])


# ── Vorauszahlungen laut Bescheid (v37) ─────────────────────────────────────

def _vz(db: sqlite3.Connection, email: str, jahr: int) -> dict:
    arten = {"est": [None] * 4, "gewst": [None] * 4}
    for r in db.execute("SELECT art, quartal, betrag_cent FROM vorauszahlung WHERE email = ? AND jahr = ?", (email, jahr)):
        arten[r["art"]][r["quartal"] - 1] = r["betrag_cent"]
    termine = {a: [vz_faellig(a, jahr, q) for q in range(1, 5)] for a in arten}
    return {
        "jahr": jahr, "arten": arten, "termine": termine,
        "summe_cent": {a: sum(x or 0 for x in v) for a, v in arten.items()},
    }


@router.get("/vorauszahlungen")
def vorauszahlungen(jahr: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    return _vz(db, user["email"], jahr)


class VorauszahlungIn(BaseModel):
    jahr: int = Field(ge=2020, le=2100)
    art: str = Field(pattern="^(est|gewst)$")
    betraege: list[int | None] = Field(min_length=4, max_length=4)  # Cent je Quartal, null/0 = keine


@router.put("/vorauszahlungen")
def vorauszahlungen_setzen(body: VorauszahlungIn, user: dict = Depends(get_current_user),
                           db: sqlite3.Connection = Depends(get_db)):
    for q, b in enumerate(body.betraege, start=1):
        if b is not None and not (0 <= b <= 100_000_000):
            raise HTTPException(400, "Betrag ungültig.")
        if b:
            db.execute(
                "INSERT INTO vorauszahlung (email, art, jahr, quartal, betrag_cent) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(email, art, jahr, quartal) DO UPDATE SET betrag_cent = excluded.betrag_cent, "
                "updated_at = datetime('now')",
                (user["email"], body.art, body.jahr, q, b),
            )
        else:
            db.execute("DELETE FROM vorauszahlung WHERE email = ? AND art = ? AND jahr = ? AND quartal = ?",
                       (user["email"], body.art, body.jahr, q))
    db.commit()
    # Schon bezahlte Raten gleich auf dem Konto suchen (sonst erst beim nächsten Stundenlauf)
    from ..services import auto_zuordnung as auto  # Zirkel vermeiden

    erkannt = 0
    for g in _gewerbe(db, user["email"]):
        try:
            erkannt += auto.lauf(db, g["id"], user, bilder=False).get("erkannt", 0)
        except Exception:
            db.rollback()
            logging.getLogger("tab.auto_zuordnung").exception("Lauf nach Vorauszahlungen fehlgeschlagen")
    return {**_vz(db, user["email"], body.jahr), "erkannt": erkannt}


# ── Kalender-Abo ────────────────────────────────────────────────────────────

@router.post("/kalender")
def kalender_erzeugen(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Neuen Abo-Link erzeugen (der alte wird ungültig). Der Pfad kommt nur diesmal zurück."""
    token = secrets.token_urlsafe(32)
    db.execute(
        "INSERT INTO frist_einstellung (email, kalender_token_hash, kalender_seit) VALUES (?, ?, ?) "
        "ON CONFLICT(email) DO UPDATE SET kalender_token_hash = excluded.kalender_token_hash, "
        "kalender_seit = excluded.kalender_seit, updated_at = datetime('now')",
        (user["email"], _hash(token), _heute()),
    )
    db.commit()
    return {"pfad": f"/api/fristen/kalender/{token}.ics"}


@router.delete("/kalender", status_code=204)
def kalender_beenden(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    db.execute(
        "UPDATE frist_einstellung SET kalender_token_hash = NULL, kalender_seit = NULL, "
        "updated_at = datetime('now') WHERE email = ?",
        (user["email"],),
    )
    db.commit()


@router.get("/kalender/{token}.ics")
def kalender_feed(token: str, db: sqlite3.Connection = Depends(get_db)):
    """iCal-Feed für Kalender-Apps — ohne Login, geschützt durch den geheimen Link."""
    r = db.execute(
        "SELECT email, est_vorauszahlung FROM frist_einstellung WHERE kalender_token_hash = ?",
        (_hash(token),),
    ).fetchone()
    if r is None:
        raise HTTPException(404, "Kalender nicht gefunden.")
    items = steuerfristen(
        db,
        email=r["email"],
        gewerbe=_gewerbe(db, r["email"]),
        heute=_heute(),
        est_vorauszahlung=bool(r["est_vorauszahlung"]),
    )
    return Response(
        content=kalender_ics(items),
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "no-store", "Content-Disposition": 'inline; filename="tab-fristen.ics"'},
    )
