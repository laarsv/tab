"""OAuth 2.1 für den MCP-Server: damit sich Claude.ai-Connectoren und Claude Desktop verbinden können.

Rollen: Tab ist Ressourcenserver (POST /api/mcp) und eigener Autorisierungsserver. Ablauf nach der MCP-Spezifikation
(2025-06-18) mit Metadaten (RFC 9728 / RFC 8414), dynamischer Client-Registrierung (RFC 7591), Autorisierungscode +
PKCE (S256 Pflicht) und rotierenden Refresh-Tokens. Es gibt nur öffentliche Clients (kein Client-Secret).

Der Inhaber gibt auf einer Seite von Tab ausdrücklich frei (/oauth/freigabe, nur mit Anmeldung). Was ein Client dann
bekommt, ist dasselbe wie ein Zugangs-Token aus den Einstellungen: nur lesender Zugriff, gültig nur am MCP-Endpunkt.
Codes und Tokens liegen nur als SHA-256 in der Datenbank. Die .well-known-Adressen liegen am Wurzelpfad und kommen über
nginx im Frontend-Container hierher (frontend/nginx.conf).
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel

from ..auth.deps import nur_inhaber
from ..config import settings
from ..db import get_db

router = APIRouter(tags=["oauth"])

SCOPE = "tab:lesen"
CODE_SEKUNDEN = 300
ACCESS_SEKUNDEN = 3600
REFRESH_TAGE = 30
MAX_CLIENTS = 200
MAX_REDIRECTS = 5
LOOPBACK = {"localhost", "127.0.0.1", "[::1]", "::1"}
ACCESS_PREFIX, REFRESH_PREFIX = "tabo_", "tabr_"
_VERIFIER = re.compile(r"^[A-Za-z0-9\-._~]{43,128}$")


def _jetzt() -> str:
    return dt.datetime.utcnow().isoformat(timespec="seconds")


def _in(sekunden: int) -> str:
    return (dt.datetime.utcnow() + dt.timedelta(seconds=sekunden)).isoformat(timespec="seconds")


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def mcp_url() -> str:
    return settings.public_origin + "/api/mcp"


def metadaten_url() -> str:
    return settings.public_origin + "/.well-known/oauth-protected-resource"


CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, MCP-Protocol-Version"}


def _json(daten: dict, status: int = 200, extra: dict | None = None) -> JSONResponse:
    return JSONResponse(daten, status_code=status, headers={**CORS, **(extra or {})})


def _fehler(code: str, text: str, status: int = 400) -> JSONResponse:
    return _json({"error": code, "error_description": text}, status, {"Cache-Control": "no-store"})


@router.options("/.well-known/{rest:path}")
@router.options("/api/oauth/register")
@router.options("/api/oauth/token")
def _preflight():
    return Response(status_code=204, headers=CORS)


# ── Metadaten ───────────────────────────────────────────────────────────────

@router.get("/.well-known/oauth-protected-resource")
@router.get("/.well-known/oauth-protected-resource/{rest:path}")
def metadaten_ressource(rest: str = ""):
    return _json({
        "resource": mcp_url(),
        "authorization_servers": [settings.public_origin],
        "scopes_supported": [SCOPE],
        "bearer_methods_supported": ["header"],
        "resource_name": "vrwb_tab Buchhaltung (nur lesen)",
    })


@router.get("/.well-known/oauth-authorization-server")
@router.get("/.well-known/oauth-authorization-server/{rest:path}")
def metadaten_server(rest: str = ""):
    o = settings.public_origin
    return _json({
        "issuer": o,
        "authorization_endpoint": f"{o}/api/oauth/authorize",
        "token_endpoint": f"{o}/api/oauth/token",
        "registration_endpoint": f"{o}/api/oauth/register",
        "scopes_supported": [SCOPE],
        "response_types_supported": ["code"],
        "response_modes_supported": ["query"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "authorization_response_iss_parameter_supported": True,
    })


# ── Client-Registrierung ────────────────────────────────────────────────────

def _redirect_ok(uri: str) -> bool:
    if not isinstance(uri, str) or len(uri) > 300:
        return False
    u = urlparse(uri)
    if u.fragment or not u.hostname:
        return False
    if u.scheme == "https":
        return True
    return u.scheme == "http" and (u.hostname in LOOPBACK or f"[{u.hostname}]" in LOOPBACK)


def _uri_passt(registriert: list[str], angefragt: str) -> bool:
    """Exakter Vergleich; bei Loopback-Adressen darf der Port abweichen (RFC 8252)."""
    if angefragt in registriert:
        return True
    a = urlparse(angefragt)
    if a.scheme != "http" or a.hostname not in LOOPBACK:
        return False
    for r in registriert:
        u = urlparse(r)
        if u.scheme == "http" and u.hostname == a.hostname and (u.path, u.query) == (a.path, a.query):
            return True
    return False


@router.post("/api/oauth/register")
async def registrieren(request: Request, db: sqlite3.Connection = Depends(get_db)):
    try:
        body = await request.json()
    except ValueError:
        return _fehler("invalid_client_metadata", "Kein gültiges JSON.")
    if not isinstance(body, dict):
        return _fehler("invalid_client_metadata", "Ein JSON-Objekt wird erwartet.")
    uris = body.get("redirect_uris")
    if not isinstance(uris, list) or not 1 <= len(uris) <= MAX_REDIRECTS or not all(_redirect_ok(u) for u in uris):
        return _fehler("invalid_redirect_uri", "redirect_uris: 1–5 Adressen, https (oder http auf localhost).")
    if body.get("token_endpoint_auth_method") not in (None, "none"):
        return _fehler("invalid_client_metadata", "Nur öffentliche Clients (token_endpoint_auth_method = none).")
    name = str(body.get("client_name") or "MCP-Client").strip()[:80] or "MCP-Client"
    # Aufräumen: Clients ohne Zugriff, die nie freigegeben wurden, verfallen nach 2 Tagen
    db.execute(
        "DELETE FROM oauth_client WHERE created_at < datetime('now', '-2 days') "
        "AND client_id NOT IN (SELECT client_id FROM oauth_grant)"
    )
    if db.execute("SELECT COUNT(*) FROM oauth_client").fetchone()[0] >= MAX_CLIENTS:
        db.commit()
        return _fehler("temporarily_unavailable", "Zu viele registrierte Clients — bitte später erneut versuchen.", 429)
    client_id = secrets.token_urlsafe(24)
    db.execute("INSERT INTO oauth_client (client_id, name, redirect_uris) VALUES (?, ?, ?)", (client_id, name, json.dumps(uris)))
    db.commit()
    return _json({
        "client_id": client_id, "client_name": name, "redirect_uris": uris, "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "client_id_issued_at": int(dt.datetime.utcnow().timestamp()),
    }, 201, {"Cache-Control": "no-store"})


def _client(db: sqlite3.Connection, client_id: str | None) -> sqlite3.Row | None:
    if not client_id:
        return None
    return db.execute("SELECT * FROM oauth_client WHERE client_id = ?", (client_id,)).fetchone()


# ── Autorisierung ───────────────────────────────────────────────────────────

class Anfrage(BaseModel):
    client_id: str
    redirect_uri: str
    code_challenge: str
    state: str | None = None
    scope: str | None = None
    resource: str | None = None


def _anfrage_pruefen(db: sqlite3.Connection, a: Anfrage) -> tuple[sqlite3.Row, str | None]:
    """Gibt (Client, Fehlercode) zurück. Ohne gültigen Client/redirect_uri wird NICHT weitergeleitet (HTTPException)."""
    c = _client(db, a.client_id)
    if c is None or not _uri_passt(json.loads(c["redirect_uris"]), a.redirect_uri):
        raise HTTPException(400, "Unbekannter Client oder nicht registrierte Weiterleitungsadresse.")
    if not re.fullmatch(r"[A-Za-z0-9\-_]{43}", a.code_challenge or ""):
        return c, "invalid_request"
    if a.scope and not set(a.scope.split()) <= {SCOPE}:
        return c, "invalid_scope"
    if a.resource and a.resource.rstrip("/") not in (mcp_url(), settings.public_origin):
        return c, "invalid_target"
    return c, None


def _zurueck(redirect_uri: str, state: str | None, **params) -> str:
    u = urlparse(redirect_uri)
    q = parse_qsl(u.query) + [(k, v) for k, v in params.items() if v is not None]
    if state:
        q.append(("state", state))
    q.append(("iss", settings.public_origin))
    return urlunparse(u._replace(query=urlencode(q)))


@router.get("/api/oauth/authorize")
def autorisieren(request: Request, db: sqlite3.Connection = Depends(get_db)):
    q = request.query_params
    try:
        a = Anfrage(client_id=q.get("client_id", ""), redirect_uri=q.get("redirect_uri", ""),
                    code_challenge=q.get("code_challenge", ""), state=q.get("state"), scope=q.get("scope"), resource=q.get("resource"))
        c, fehler = _anfrage_pruefen(db, a)
    except HTTPException as e:
        return PlainTextResponse(str(e.detail), status_code=400)
    if q.get("response_type") != "code":
        fehler = "unsupported_response_type"
    elif q.get("code_challenge_method") != "S256":
        fehler = "invalid_request"
    if fehler:
        return RedirectResponse(_zurueck(a.redirect_uri, a.state, error=fehler), status_code=302)
    ziel = {k: v for k, v in a.model_dump().items() if v}
    return RedirectResponse(f"{settings.public_origin}/oauth/freigabe?{urlencode(ziel)}", status_code=302)


@router.get("/api/oauth/freigabe/info")
def freigabe_info(client_id: str, redirect_uri: str, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    c = _client(db, client_id)
    if c is None or not _uri_passt(json.loads(c["redirect_uris"]), redirect_uri):
        raise HTTPException(404, "Diese Anfrage ist ungültig oder abgelaufen.")
    host = urlparse(redirect_uri).hostname or ""
    return {"client_name": c["name"], "ziel": host, "scope": SCOPE, "konto": user["email"]}


class FreigabeIn(Anfrage):
    erlauben: bool
    vorschlaege: bool = False  # Stufe „Vorschläge machen“ — standardmäßig aus


@router.post("/api/oauth/freigabe")
def freigeben(body: FreigabeIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    try:
        c, fehler = _anfrage_pruefen(db, body)
    except HTTPException:
        raise HTTPException(400, "Diese Anfrage ist ungültig oder abgelaufen.")
    if fehler:
        return {"redirect": _zurueck(body.redirect_uri, body.state, error=fehler)}
    if not body.erlauben:
        return {"redirect": _zurueck(body.redirect_uri, body.state, error="access_denied")}
    code = secrets.token_urlsafe(32)
    db.execute("DELETE FROM oauth_code WHERE expires_at < ?", (_jetzt(),))
    db.execute(
        "INSERT INTO oauth_code (code_hash, client_id, owner_email, redirect_uri, code_challenge, expires_at, vorschlaege) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (_hash(code), c["client_id"], user["email"], body.redirect_uri, body.code_challenge, _in(CODE_SEKUNDEN), 1 if body.vorschlaege else 0),
    )
    db.commit()
    return {"redirect": _zurueck(body.redirect_uri, body.state, code=code)}


# ── Token ───────────────────────────────────────────────────────────────────

def _neue_tokens(db: sqlite3.Connection, client_id: str, owner: str, code_hash: str | None, grant_id: int | None = None, vorschlaege: int = 0) -> dict:
    access, refresh = ACCESS_PREFIX + secrets.token_urlsafe(32), REFRESH_PREFIX + secrets.token_urlsafe(32)
    if grant_id is None:
        db.execute(
            "INSERT INTO oauth_grant (client_id, owner_email, access_hash, access_expires, refresh_hash, refresh_expires, code_hash, vorschlaege) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (client_id, owner, _hash(access), _in(ACCESS_SEKUNDEN), _hash(refresh), _in(REFRESH_TAGE * 86400), code_hash, vorschlaege),
        )
    else:  # Rotation: derselbe Zugriff, neue Tokens — das alte Refresh-Token ist damit tot
        db.execute(
            "UPDATE oauth_grant SET access_hash = ?, access_expires = ?, refresh_hash = ?, refresh_expires = ? WHERE id = ?",
            (_hash(access), _in(ACCESS_SEKUNDEN), _hash(refresh), _in(REFRESH_TAGE * 86400), grant_id),
        )
    db.commit()
    return {"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_SEKUNDEN, "refresh_token": refresh, "scope": SCOPE}


@router.post("/api/oauth/token")
async def token(request: Request, db: sqlite3.Connection = Depends(get_db)):
    try:
        f = dict((await request.form()).items())
    except Exception:
        return _fehler("invalid_request", "Erwartet wird application/x-www-form-urlencoded.")
    jetzt = _jetzt()
    db.execute("DELETE FROM oauth_grant WHERE refresh_expires < ?", (jetzt,))
    db.commit()
    typ, client_id = f.get("grant_type"), f.get("client_id")
    c = _client(db, client_id)
    if c is None:
        return _fehler("invalid_client", "Unbekannter Client.", 401)
    kopf = {"Cache-Control": "no-store", "Pragma": "no-cache"}

    if typ == "authorization_code":
        code, verifier, uri = f.get("code"), f.get("code_verifier") or "", f.get("redirect_uri")
        if not code or not uri:
            return _fehler("invalid_request", "code und redirect_uri werden gebraucht.")
        row = db.execute("SELECT * FROM oauth_code WHERE code_hash = ?", (_hash(code),)).fetchone()
        if row is None or row["client_id"] != c["client_id"] or row["redirect_uri"] != uri:
            return _fehler("invalid_grant", "Der Code ist ungültig.")
        if row["used"]:
            # Wiederverwendung eines Codes: alles widerrufen, was daraus entstanden ist
            db.execute("DELETE FROM oauth_grant WHERE code_hash = ?", (row["code_hash"],))
            db.commit()
            return _fehler("invalid_grant", "Der Code wurde schon benutzt.")
        if row["expires_at"] < jetzt:
            return _fehler("invalid_grant", "Der Code ist abgelaufen.")
        erwartet = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        if not _VERIFIER.match(verifier) or not hmac.compare_digest(erwartet, row["code_challenge"]):
            return _fehler("invalid_grant", "code_verifier passt nicht (PKCE).")
        db.execute("UPDATE oauth_code SET used = 1 WHERE code_hash = ?", (row["code_hash"],))
        return _json(_neue_tokens(db, c["client_id"], row["owner_email"], row["code_hash"], None, row["vorschlaege"]), 200, kopf)

    if typ == "refresh_token":
        rt = f.get("refresh_token") or ""
        g = db.execute("SELECT * FROM oauth_grant WHERE refresh_hash = ?", (_hash(rt),)).fetchone() if rt else None
        if g is None or g["client_id"] != c["client_id"]:
            return _fehler("invalid_grant", "Das Refresh-Token ist ungültig oder abgelaufen.")
        return _json(_neue_tokens(db, c["client_id"], g["owner_email"], g["code_hash"], g["id"]), 200, kopf)

    return _fehler("unsupported_grant_type", "Unterstützt: authorization_code, refresh_token.")


# ── Verbundene Apps (Inhaber) ───────────────────────────────────────────────

@router.get("/api/oauth/grants")
def grants(user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    return [
        {"id": r["id"], "client_name": r["name"], "created_at": r["created_at"], "letzte_nutzung": r["letzte_nutzung"], "vorschlaege": bool(r["vorschlaege"])}
        for r in db.execute(
            "SELECT g.*, c.name FROM oauth_grant g JOIN oauth_client c ON c.client_id = g.client_id "
            "WHERE g.owner_email = ? ORDER BY g.created_at, g.id", (user["email"],))
    ]


class StufeIn(BaseModel):
    vorschlaege: bool


@router.patch("/api/oauth/grants/{grant_id}")
def grant_stufe(grant_id: int, body: StufeIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("UPDATE oauth_grant SET vorschlaege = ? WHERE id = ? AND owner_email = ?", (1 if body.vorschlaege else 0, grant_id, user["email"]))
    if cur.rowcount == 0:
        raise HTTPException(404, "Zugriff nicht gefunden.")
    db.commit()
    return {"id": grant_id, "vorschlaege": body.vorschlaege}


@router.delete("/api/oauth/grants/{grant_id}", status_code=204)
def grant_widerrufen(grant_id: int, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("DELETE FROM oauth_grant WHERE id = ? AND owner_email = ?", (grant_id, user["email"]))
    if cur.rowcount == 0:
        raise HTTPException(404, "Zugriff nicht gefunden.")
    db.commit()
