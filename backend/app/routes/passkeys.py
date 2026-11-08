"""Passkeys (WebAuthn): Anmeldung mit Fingerabdruck/Gesicht/Geräte-PIN statt Passwort.

Zusätzlicher Anmeldeweg für Google- und Passwort-Konten: wer angemeldet ist, hinterlegt Passkeys für sein Konto
(E-Mail); auf der Anmeldeseite genügt dann „Mit Passkey anmelden“ (auffindbarer Passkey, kein Benutzername nötig).
Die Prüfung macht die Bibliothek py_webauthn. Der Passkey ersetzt das Passwort, deshalb verlangen wir Nutzerprüfung
(Biometrie/PIN, userVerification = required). Challenges liegen im Speicher (ein Prozess), gelten 5 Minuten und
genau einmal. Die Steuerberatung hat hier nichts verloren (nur_inhaber; zusätzlich sperrt sie die Allowlist).
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from ..auth.cookies import set_session_cookie
from ..auth.deps import nur_inhaber
from ..auth.session import encode_session
from ..config import settings
from ..db import get_db

router = APIRouter(prefix="/api/passkeys", tags=["passkeys"])

MAX_PASSKEYS = 10
CHALLENGE_SEKUNDEN = 300
_challenges: dict[str, tuple[bytes, str | None, float]] = {}  # id -> (challenge, email|None, gültig_bis)
_lock = threading.Lock()


def _challenge_ablegen(challenge: bytes, email: str | None) -> str:
    cid = secrets.token_urlsafe(24)
    jetzt = time.time()
    with _lock:
        for k in [k for k, v in _challenges.items() if v[2] < jetzt]:
            del _challenges[k]
        _challenges[cid] = (challenge, email, jetzt + CHALLENGE_SEKUNDEN)
    return cid


def _challenge_holen(cid: str, email: str | None) -> bytes:
    """Genau einmal einlösbar; gehört bei der Registrierung zum angemeldeten Konto."""
    with _lock:
        eintrag = _challenges.pop(cid, None)
    if eintrag is None or eintrag[2] < time.time() or eintrag[1] != email:
        raise HTTPException(400, "Die Anfrage ist abgelaufen — bitte noch einmal versuchen.")
    return eintrag[0]


def _row(r: sqlite3.Row) -> dict:
    return {"id": r["id"], "name": r["name"], "created_at": r["created_at"], "letzte_nutzung": r["letzte_nutzung"]}


# ── Verwalten (angemeldet) ──────────────────────────────────────────────────

@router.get("")
def liste(user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    return [
        _row(r) for r in db.execute("SELECT * FROM passkey WHERE email = ? ORDER BY created_at, id", (user["email"],))
    ]


@router.post("/registrierung/optionen")
def registrierung_optionen(user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    vorhanden = db.execute("SELECT credential_id, transports FROM passkey WHERE email = ?", (user["email"],)).fetchall()
    if len(vorhanden) >= MAX_PASSKEYS:
        raise HTTPException(400, f"Mehr als {MAX_PASSKEYS} Passkeys sind nicht möglich — entferne zuerst einen.")
    opts = generate_registration_options(
        rp_id=settings.passkey_rp_id,
        rp_name="vrwb_tab",
        user_id=hashlib.sha256(user["email"].encode()).digest(),
        user_name=user["email"],
        user_display_name=user.get("name") or user["email"],
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(r["credential_id"])) for r in vorhanden],
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.REQUIRED,  # auffindbar: Anmelden ohne E-Mail-Eingabe
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )
    return {"challenge_id": _challenge_ablegen(opts.challenge, user["email"]), "options": json.loads(options_to_json(opts))}


class RegistrierenIn(BaseModel):
    challenge_id: str
    credential: dict
    name: str = Field(default="", max_length=60)


@router.post("/registrierung", status_code=201)
def registrieren(body: RegistrierenIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    challenge = _challenge_holen(body.challenge_id, user["email"])
    try:
        v = verify_registration_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=settings.passkey_rp_id,
            expected_origin=settings.passkey_origin,
            require_user_verification=True,
        )
    except Exception:  # jede Art von Fehlschlag (auch kaputtes JSON/Base64) → dieselbe Antwort, keine Details
        raise HTTPException(400, "Der Passkey konnte nicht bestätigt werden.")
    cid = bytes_to_base64url(v.credential_id)
    if db.execute("SELECT 1 FROM passkey WHERE credential_id = ?", (cid,)).fetchone():
        raise HTTPException(400, "Dieser Passkey ist schon hinterlegt.")
    transports = body.credential.get("response", {}).get("transports")
    n = db.execute("SELECT COUNT(*) FROM passkey WHERE email = ?", (user["email"],)).fetchone()[0]
    cur = db.execute(
        "INSERT INTO passkey (email, name, inhaber_name, credential_id, public_key, sign_count, transports) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            user["email"],
            body.name.strip() or f"Passkey {n + 1}",
            user.get("name"),
            cid,
            v.credential_public_key,
            v.sign_count,
            json.dumps(transports) if isinstance(transports, list) else None,
        ),
    )
    db.commit()
    return _row(db.execute("SELECT * FROM passkey WHERE id = ?", (cur.lastrowid,)).fetchone())


class UmbenennenIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)


@router.patch("/{passkey_id}")
def umbenennen(passkey_id: int, body: UmbenennenIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("UPDATE passkey SET name = ? WHERE id = ? AND email = ?", (body.name.strip(), passkey_id, user["email"]))
    if cur.rowcount == 0:
        raise HTTPException(404, "Passkey nicht gefunden.")
    db.commit()
    return _row(db.execute("SELECT * FROM passkey WHERE id = ?", (passkey_id,)).fetchone())


@router.delete("/{passkey_id}", status_code=204)
def entfernen(passkey_id: int, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("DELETE FROM passkey WHERE id = ? AND email = ?", (passkey_id, user["email"]))
    if cur.rowcount == 0:
        raise HTTPException(404, "Passkey nicht gefunden.")
    db.commit()


# ── Anmelden (öffentlich) ───────────────────────────────────────────────────

@router.post("/anmeldung/optionen")
def anmeldung_optionen():
    opts = generate_authentication_options(
        rp_id=settings.passkey_rp_id, user_verification=UserVerificationRequirement.REQUIRED
    )
    return {"challenge_id": _challenge_ablegen(opts.challenge, None), "options": json.loads(options_to_json(opts))}


class AnmeldenIn(BaseModel):
    challenge_id: str
    credential: dict


@router.post("/anmeldung", status_code=204)
def anmelden(body: AnmeldenIn, db: sqlite3.Connection = Depends(get_db)):
    challenge = _challenge_holen(body.challenge_id, None)
    falsch = HTTPException(400, "Anmeldung mit Passkey fehlgeschlagen.")
    cid = body.credential.get("id")
    row = db.execute("SELECT * FROM passkey WHERE credential_id = ?", (cid,)).fetchone() if isinstance(cid, str) else None
    if row is None:
        raise falsch
    try:
        v = verify_authentication_response(
            credential=body.credential,
            expected_challenge=challenge,
            expected_rp_id=settings.passkey_rp_id,
            expected_origin=settings.passkey_origin,
            credential_public_key=bytes(row["public_key"]),
            credential_current_sign_count=row["sign_count"],
            require_user_verification=True,
        )
    except Exception:
        raise falsch
    email = row["email"]
    # dieselbe Zugangsregel wie bei Google/Passwort: Entzug in ALLOWED_EMAILS wirkt auch hier
    if not settings.OPEN_SIGNUP and not settings.is_email_allowed(email):
        raise HTTPException(403, "Diese Adresse ist nicht freigeschaltet.")
    db.execute(
        "UPDATE passkey SET sign_count = ?, letzte_nutzung = datetime('now') WHERE id = ?", (v.new_sign_count, row["id"])
    )
    db.commit()
    response = Response(status_code=204)
    set_session_cookie(response, encode_session(email, name=row["inhaber_name"] or email, picture=None))
    return response
