"""Login: Google-OAuth (Redirect → Callback → Session-Cookie) und — falls ein
System-Mail-Absender konfiguriert ist — E-Mail + Passwort mit Code-Verifizierung."""
from __future__ import annotations

import sqlite3
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from ..config import settings
from ..db import get_db
from .cookies import clear_session_cookie, set_session_cookie
from .deps import get_current_user
from .google import oauth
from .local import (
    code_gueltig,
    erfolg,
    fehlversuch,
    gesperrt,
    hash_passwort,
    neuer_code,
    sende_system_mail,
    verify_passwort,
)
from .session import encode_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request):
    return await oauth.google.authorize_redirect(request, settings.OAUTH_REDIRECT_URI)


@router.get("/callback")
async def callback(request: Request):
    frontend = settings.FRONTEND_URL.rstrip("/") or ""
    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        return RedirectResponse(f"{frontend}/login?{urlencode({'error': 'oauth_failed'})}")

    userinfo = token.get("userinfo") or await oauth.google.userinfo(token=token)
    email = (userinfo.get("email") or "").lower()
    name = userinfo.get("name") or email
    picture = userinfo.get("picture")

    # Bei offener Registrierung nur verifizierte Google-Identitäten (wichtig für
    # Google-Konten mit externer Adresse, z. B. lars@vrwb.de); sonst Allowlist.
    if not email or userinfo.get("email_verified") is False:
        return RedirectResponse(f"{frontend}/login?{urlencode({'error': 'not_allowed'})}")
    if not settings.OPEN_SIGNUP and not settings.is_email_allowed(email):
        return RedirectResponse(f"{frontend}/login?{urlencode({'error': 'not_allowed'})}")

    response = RedirectResponse(settings.FRONTEND_URL or "/")
    set_session_cookie(response, encode_session(email, name=name, picture=picture))
    return response


@router.post("/logout", status_code=204)
async def logout():
    response = Response(status_code=204)
    clear_session_cookie(response)
    return response


# ── E-Mail + Passwort (unabhängig von Google) ───────────────────────────────────


@router.get("/methoden")
def methoden():
    """Welche Login-Wege sind aktiv? (Frontend blendet das Passwort-Formular ein.)"""
    return {"google": True, "passwort": settings.system_mail_konfiguriert}


class RegisterIn(BaseModel):
    email: str = Field(min_length=5, max_length=200)
    passwort: str = Field(min_length=8, max_length=200)
    name: str | None = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def _v_mail(cls, v: str) -> str:
        v = v.strip().lower()
        if "@" not in v or " " in v or "." not in v.split("@")[-1]:
            raise ValueError("Bitte eine gültige E-Mail-Adresse angeben.")
        return v


class CodeIn(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)


class PasswortLoginIn(BaseModel):
    email: str
    passwort: str


class ResetIn(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)
    passwort: str = Field(min_length=8, max_length=200)


def _passwort_login_verfuegbar():
    if not settings.system_mail_konfiguriert:
        raise HTTPException(400, "Anmeldung per E-Mail/Passwort ist hier nicht aktiviert.")


def _cookie_antwort(email: str, name: str | None) -> Response:
    response = Response(status_code=204)
    set_session_cookie(response, encode_session(email, name=name or email, picture=None))
    return response


@router.post("/register", status_code=204)
def register(body: RegisterIn, db: sqlite3.Connection = Depends(get_db)):
    _passwort_login_verfuegbar()
    if not settings.OPEN_SIGNUP and not settings.is_email_allowed(body.email):
        raise HTTPException(400, "Diese Adresse ist nicht freigeschaltet.")
    bestehend = db.execute("SELECT * FROM nutzer WHERE email = ?", (body.email,)).fetchone()
    if bestehend and bestehend["verifiziert"]:
        raise HTTPException(400, "Konto existiert bereits — einloggen oder Passwort zurücksetzen.")
    code, bis = neuer_code()
    db.execute(
        """
        INSERT INTO nutzer (email, passwort_hash, name, verifiziert, verify_code, verify_gueltig_bis)
        VALUES (?, ?, ?, 0, ?, ?)
        ON CONFLICT(email) DO UPDATE SET passwort_hash=excluded.passwort_hash,
            name=excluded.name, verify_code=excluded.verify_code,
            verify_gueltig_bis=excluded.verify_gueltig_bis, updated_at=datetime('now')
        """,
        (body.email, hash_passwort(body.passwort), (body.name or "").strip() or None, code, bis),
    )
    db.commit()
    try:
        sende_system_mail(
            body.email,
            "Tab: Bestätigungscode",
            f"Dein Bestätigungscode für tab.vrwb.de: {code}\n\n"
            f"Der Code ist 30 Minuten gültig. Falls du dich nicht registriert hast, "
            f"ignoriere diese Mail einfach.",
        )
    except Exception:
        raise HTTPException(502, "Bestätigungs-Mail konnte nicht gesendet werden — später erneut versuchen.")


@router.post("/verify")
def verify(body: CodeIn, db: sqlite3.Connection = Depends(get_db)):
    _passwort_login_verfuegbar()
    email = body.email.strip().lower()
    n = db.execute("SELECT * FROM nutzer WHERE email = ?", (email,)).fetchone()
    if n is None or not code_gueltig(body.code, n["verify_code"], n["verify_gueltig_bis"]):
        raise HTTPException(400, "Code ungültig oder abgelaufen.")
    db.execute(
        "UPDATE nutzer SET verifiziert=1, verify_code=NULL, verify_gueltig_bis=NULL, "
        "updated_at=datetime('now') WHERE email = ?",
        (email,),
    )
    db.commit()
    return _cookie_antwort(email, n["name"])


@router.post("/passwort-login")
def passwort_login(body: PasswortLoginIn, db: sqlite3.Connection = Depends(get_db)):
    _passwort_login_verfuegbar()
    email = body.email.strip().lower()
    if gesperrt(email):
        raise HTTPException(429, "Zu viele Fehlversuche — bitte 15 Minuten warten.")
    n = db.execute("SELECT * FROM nutzer WHERE email = ?", (email,)).fetchone()
    if n is None or not n["verifiziert"] or not verify_passwort(body.passwort, n["passwort_hash"]):
        fehlversuch(email)
        raise HTTPException(400, "E-Mail oder Passwort falsch.")
    if not settings.OPEN_SIGNUP and not settings.is_email_allowed(email):
        raise HTTPException(400, "Diese Adresse ist nicht freigeschaltet.")
    erfolg(email)
    return _cookie_antwort(email, n["name"])


class ResetAnfordernIn(BaseModel):
    email: str


@router.post("/reset-anfordern", status_code=204)
def reset_anfordern(body: ResetAnfordernIn, db: sqlite3.Connection = Depends(get_db)):
    """Antwortet immer 204 (kein Nutzer-Enumerieren); Code geht nur an bekannte Konten."""
    _passwort_login_verfuegbar()
    email = body.email.strip().lower()
    n = db.execute("SELECT * FROM nutzer WHERE email = ?", (email,)).fetchone()
    if n is None:
        return
    code, bis = neuer_code()
    db.execute(
        "UPDATE nutzer SET reset_code=?, reset_gueltig_bis=?, updated_at=datetime('now') "
        "WHERE email = ?",
        (code, bis, email),
    )
    db.commit()
    try:
        sende_system_mail(
            email,
            "Tab: Passwort zurücksetzen",
            f"Dein Code zum Zurücksetzen des Passworts: {code}\n\n"
            f"Der Code ist 30 Minuten gültig. Falls du das nicht angefordert hast, "
            f"ignoriere diese Mail — dein Passwort bleibt unverändert.",
        )
    except Exception:
        pass  # bewusst still: keine Rückschlüsse auf Kontoexistenz


@router.post("/reset", status_code=204)
def reset(body: ResetIn, db: sqlite3.Connection = Depends(get_db)):
    _passwort_login_verfuegbar()
    email = body.email.strip().lower()
    n = db.execute("SELECT * FROM nutzer WHERE email = ?", (email,)).fetchone()
    if n is None or not code_gueltig(body.code, n["reset_code"], n["reset_gueltig_bis"]):
        raise HTTPException(400, "Code ungültig oder abgelaufen.")
    db.execute(
        "UPDATE nutzer SET passwort_hash=?, reset_code=NULL, reset_gueltig_bis=NULL, "
        "verifiziert=1, updated_at=datetime('now') WHERE email = ?",
        (hash_passwort(body.passwort), email),
    )
    db.commit()
    erfolg(email)


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user
