"""Zugang für die Steuerberatung (nur lesen) — Aufbau nach Haben, eigenständig umgesetzt.

Ablauf: Der Inhaber erzeugt einen Einladungslink (einmal sichtbar, gespeichert ist nur der SHA-256-Hash, einmal
einlösbar, 72 Stunden gültig). Die Steuerberatung legt damit ihr Konto an (Name, E-Mail, Passwort ab 12 Zeichen) und
meldet sich künftig unter /api/berater/login an. Ihre Sitzung trägt die E-Mail des Inhabers (so greifen alle
Mandanten-Guards) plus „berater“ = Zugangs-ID; was sie darf, regelt auth/berater_guard.py. Sperren und Entfernen
wirken sofort, weil get_current_user den Zugang bei jeder Anfrage prüft.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from ..auth import local
from ..auth.cookies import set_session_cookie
from ..auth.deps import nur_inhaber
from ..auth.session import encode_session
from ..db import get_db

router = APIRouter(prefix="/api/berater", tags=["berater"])

EINLADUNG_STUNDEN = 72
MIN_PASSWORT = 12
_DUMMY_HASH = local.hash_passwort("kein-konto")  # gleiche Rechenzeit, auch wenn die E-Mail unbekannt ist


def _jetzt() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _mail(v: str) -> str:
    v = v.strip().lower()
    if "@" not in v or " " in v or "." not in v.split("@")[-1] or len(v) > 200:
        raise ValueError("Bitte eine gültige E-Mail-Adresse angeben.")
    return v


# ── Inhaber: Zugänge verwalten ──────────────────────────────────────────────

class EinladungIn(BaseModel):
    bezeichnung: str = Field(min_length=1, max_length=120)  # z. B. der Name der Kanzlei


@router.get("")
def uebersicht(user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    jetzt = _jetzt()
    zugaenge = [
        {
            "id": r["id"], "bezeichnung": r["bezeichnung"], "name": r["name"], "email": r["email"],
            "gesperrt": bool(r["gesperrt"]), "letzte_anmeldung": r["letzte_anmeldung"], "created_at": r["created_at"],
        }
        for r in db.execute(
            "SELECT * FROM berater_zugang WHERE owner_email = ? ORDER BY created_at, id", (user["email"],)
        )
    ]
    einladungen = [
        {"id": r["id"], "bezeichnung": r["bezeichnung"], "expires_at": r["expires_at"], "created_at": r["created_at"]}
        for r in db.execute(
            "SELECT * FROM berater_einladung WHERE owner_email = ? AND eingeloest_am IS NULL AND expires_at > ? "
            "ORDER BY created_at DESC, id DESC",
            (user["email"], jetzt),
        )
    ]
    return {"zugaenge": zugaenge, "einladungen": einladungen, "gueltig_stunden": EINLADUNG_STUNDEN}


@router.post("/einladungen", status_code=201)
def einladen(body: EinladungIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    """Erzeugt den Link. Das Token steht nur in dieser Antwort — gespeichert wird allein der Hash."""
    token = secrets.token_urlsafe(32)
    bis = (dt.datetime.utcnow() + dt.timedelta(hours=EINLADUNG_STUNDEN)).isoformat(timespec="seconds")
    cur = db.execute(
        "INSERT INTO berater_einladung (owner_email, bezeichnung, token_hash, expires_at) VALUES (?, ?, ?, ?)",
        (user["email"], body.bezeichnung.strip(), _hash(token), bis),
    )
    db.commit()
    return {"id": cur.lastrowid, "token": token, "expires_at": bis, "bezeichnung": body.bezeichnung.strip()}


@router.delete("/einladungen/{einladung_id}", status_code=204)
def einladung_zurueckziehen(einladung_id: int, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute(
        "DELETE FROM berater_einladung WHERE id = ? AND owner_email = ? AND eingeloest_am IS NULL",
        (einladung_id, user["email"]),
    )
    if cur.rowcount == 0:
        raise HTTPException(404, "Einladung nicht gefunden.")
    db.commit()


class SperreIn(BaseModel):
    gesperrt: bool


def _zugang(db: sqlite3.Connection, user: dict, zugang_id: int) -> sqlite3.Row:
    row = db.execute(
        "SELECT * FROM berater_zugang WHERE id = ? AND owner_email = ?", (zugang_id, user["email"])
    ).fetchone()
    if row is None:
        raise HTTPException(404, "Zugang nicht gefunden.")
    return row


@router.post("/zugaenge/{zugang_id}/sperre")
def sperren(zugang_id: int, body: SperreIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    _zugang(db, user, zugang_id)
    db.execute("UPDATE berater_zugang SET gesperrt = ? WHERE id = ?", (1 if body.gesperrt else 0, zugang_id))
    db.commit()
    return {"id": zugang_id, "gesperrt": body.gesperrt}


@router.delete("/zugaenge/{zugang_id}", status_code=204)
def entfernen(zugang_id: int, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    _zugang(db, user, zugang_id)
    db.execute("DELETE FROM berater_zugang WHERE id = ?", (zugang_id,))
    db.commit()


# ── Steuerberatung: einladen annehmen, anmelden ─────────────────────────────

def _offene_einladung(db: sqlite3.Connection, token: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM berater_einladung WHERE token_hash = ?", (_hash(token),)).fetchone()
    if row is None or row["eingeloest_am"] is not None or row["expires_at"] <= _jetzt():
        # eine Meldung für alle Fälle: nicht verraten, ob es das Token je gab
        raise HTTPException(404, "Dieser Einladungslink ist ungültig oder abgelaufen.")
    return row


@router.get("/einladung/{token}")
def einladung_ansehen(token: str, db: sqlite3.Connection = Depends(get_db)):
    e = _offene_einladung(db, token)
    return {"bezeichnung": e["bezeichnung"], "expires_at": e["expires_at"]}


class AnnehmenIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str
    passwort: str = Field(min_length=MIN_PASSWORT, max_length=200)

    @field_validator("email")
    @classmethod
    def _v_mail(cls, v: str) -> str:
        return _mail(v)


def _cookie(zugang_id: int, owner_email: str, name: str) -> Response:
    response = Response(status_code=204)
    set_session_cookie(response, encode_session(owner_email, name=name, berater=zugang_id))
    return response


@router.post("/einladung/{token}/annehmen", status_code=204)
def annehmen(token: str, body: AnnehmenIn, db: sqlite3.Connection = Depends(get_db)):
    e = _offene_einladung(db, token)
    if body.email == e["owner_email"].lower():
        raise HTTPException(400, "Bitte eine andere E-Mail-Adresse als die des Inhabers verwenden.")
    if db.execute("SELECT 1 FROM berater_zugang WHERE email = ?", (body.email,)).fetchone():
        raise HTTPException(400, "Zu dieser E-Mail-Adresse gibt es schon einen Zugang.")
    cur = db.execute(
        "INSERT INTO berater_zugang (owner_email, bezeichnung, name, email, passwort_hash, letzte_anmeldung) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (e["owner_email"], e["bezeichnung"], body.name.strip(), body.email, local.hash_passwort(body.passwort), _jetzt()),
    )
    db.execute("UPDATE berater_einladung SET eingeloest_am = ? WHERE id = ?", (_jetzt(), e["id"]))
    db.commit()
    return _cookie(cur.lastrowid, e["owner_email"], body.name.strip())


class LoginIn(BaseModel):
    email: str
    passwort: str = Field(max_length=200)


@router.post("/login", status_code=204)
def login(body: LoginIn, request: Request, db: sqlite3.Connection = Depends(get_db)):
    email = body.email.strip().lower()
    schluessel = f"berater:{email}"
    if local.gesperrt(schluessel):
        raise HTTPException(429, "Zu viele Fehlversuche — bitte 15 Minuten warten.")
    z = db.execute("SELECT * FROM berater_zugang WHERE email = ?", (email,)).fetchone()
    passt = local.verify_passwort(body.passwort, z["passwort_hash"] if z else _DUMMY_HASH)
    if z is None or not passt:
        local.fehlversuch(schluessel)
        raise HTTPException(400, "E-Mail oder Passwort falsch.")
    if z["gesperrt"]:
        raise HTTPException(403, "Dieser Zugang ist gesperrt.")
    local.erfolg(schluessel)
    db.execute("UPDATE berater_zugang SET letzte_anmeldung = ? WHERE id = ?", (_jetzt(), z["id"]))
    db.commit()
    return _cookie(z["id"], z["owner_email"], z["name"])
