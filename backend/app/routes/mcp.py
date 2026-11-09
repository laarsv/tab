"""KI-Assistenten (MCP, nur lesen) — Aufbau nach Haben, eigenständig umgesetzt.

Ein MCP-Server (Streamable HTTP, JSON-RPC 2.0) unter POST /api/mcp: Claude Code oder ein anderer Client fragt die
Buchhaltung ab (Kennzahlen, Summenblatt, Buchungen, Rechnungen, Anlagen, Fristen, Übersicht). Anmeldung nur per
Zugangs-Token (Authorization: Bearer …), das der Inhaber im Profil-Menü erzeugt; gespeichert ist nur der Hash.

Nur lesen, dreifach abgesichert: (1) es gibt nur lesende Werkzeuge, (2) die Datenbankverbindung steht auf
PRAGMA query_only — selbst ein Fehler im Code könnte nichts schreiben, (3) Tokens gelten nirgends sonst (kein Cookie, keine
andere Route akzeptiert sie), und Cookies gelten hier nicht. Die Mandantenprüfung läuft wie überall über check_gewerbe.
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import sqlite3
import threading
import time

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..auth.deps import nur_inhaber
from ..config import settings
from ..db import _connect, get_db
from . import oauth
from . import afa, belege, buchungen, export, fristen, gewerbe, kategorien, meta, rechnungen, uebersicht

router = APIRouter(prefix="/api", tags=["ki"])
log = logging.getLogger("tab.mcp")

PROTOKOLL_VERSIONEN = ["2025-06-18", "2025-03-26", "2024-11-05"]
MAX_TOKENS = 10
MAX_ZEICHEN = 60_000          # Antworten darüber werden gekürzt (und das gesagt)
ANFRAGEN_PRO_MINUTE = 120
TOKEN_PREFIX = "tabmcp_"

ANWEISUNG = (
    "Lesender Zugang zur Buchhaltung (vrwb_tab, Kleinunternehmer § 19 UStG, Einnahmen-Überschuss-Rechnung). "
    "Beträge sind ganze Cent (…_cent), Brutto = Netto. Beginne mit gewerbe_liste, dann kennzahlen oder uebersicht. "
    "Kein Steuerrat — Zahlen nennen, nicht rechtlich bewerten. Es gibt keine schreibenden Werkzeuge."
)


# ── Tokens verwalten (Inhaber, angemeldet) ──────────────────────────────────

def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("/ki/tokens")
def tokens(user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    return [
        {"id": r["id"], "name": r["name"], "created_at": r["created_at"], "letzte_nutzung": r["letzte_nutzung"]}
        for r in db.execute("SELECT * FROM ki_token WHERE owner_email = ? ORDER BY created_at, id", (user["email"],))
    ]


@router.post("/ki/tokens", status_code=201)
def token_erzeugen(body: TokenIn, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    """Das Token steht nur in dieser Antwort."""
    if db.execute("SELECT COUNT(*) FROM ki_token WHERE owner_email = ?", (user["email"],)).fetchone()[0] >= MAX_TOKENS:
        raise HTTPException(400, f"Mehr als {MAX_TOKENS} Zugänge sind nicht möglich — entferne zuerst einen.")
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    cur = db.execute(
        "INSERT INTO ki_token (owner_email, name, token_hash) VALUES (?, ?, ?)",
        (user["email"], body.name.strip(), _hash(token)),
    )
    db.commit()
    return {"id": cur.lastrowid, "name": body.name.strip(), "token": token}


@router.delete("/ki/tokens/{token_id}", status_code=204)
def token_entfernen(token_id: int, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    cur = db.execute("DELETE FROM ki_token WHERE id = ? AND owner_email = ?", (token_id, user["email"]))
    if cur.rowcount == 0:
        raise HTTPException(404, "Zugang nicht gefunden.")
    db.commit()


# ── Werkzeuge (alle nur lesend) ─────────────────────────────────────────────

class WerkzeugFehler(Exception):
    pass


def _int(a: dict, name: str, pflicht: bool = True, standard: int | None = None) -> int | None:
    v = a.get(name, standard)
    if v is None:
        if pflicht:
            raise WerkzeugFehler(f"Parameter „{name}“ fehlt.")
        return None
    if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
        raise WerkzeugFehler(f"Parameter „{name}“ muss eine ganze Zahl sein.")
    return int(v)


def _w_gewerbe(db, user, a):
    return [
        {k: g.get(k) for k in ("id", "name", "steuernummer", "besteuerung", "anschrift", "iban", "aktiv")}
        for g in gewerbe.list_gewerbe(False, user, db)
    ]


def _w_kennzahlen(db, user, a):
    return meta.kennzahlen(_int(a, "gewerbe_id"), _int(a, "jahr"), user, db)


def _w_summenblatt(db, user, a):
    return export.summenblatt(_int(a, "gewerbe_id"), _int(a, "jahr"), user, db)


def _w_buchungen(db, user, a):
    gid, jahr = _int(a, "gewerbe_id"), _int(a, "jahr")
    limit = min(max(_int(a, "limit", False, 50), 1), 200)
    suche = str(a.get("suche") or "").strip().lower()
    alle = buchungen.list_buchungen(gid, jahr, user, db)
    if suche:
        alle = [
            b for b in alle
            if suche in (b.get("beschreibung") or "").lower()
            or any(suche in (p.get("kategorie_name") or "").lower() for p in b["positionen"])
        ]
    out = [
        {
            "id": b["id"], "datum": b["datum"], "beschreibung": b["beschreibung"], "summe_cent": b["summe_cent"],
            "betrieblich_cent": b["betrieblich_cent"], "belege": b["beleg_count"],
            "positionen": [
                {"kategorie": p["kategorie_name"], "typ": p["kategorie_typ"], "betrag_cent": p["betrag_cent"], "privat_bp": p.get("privat_bp")}
                for p in b["positionen"]
            ],
        }
        for b in alle[:limit]
    ]
    return {"anzahl_gesamt": len(alle), "angezeigt": len(out), "buchungen": out}


def _w_rechnungen(db, user, a):
    status = str(a.get("status") or "").strip()
    rows = rechnungen.list_rechnungen(_int(a, "gewerbe_id"), _int(a, "jahr"), user, db)
    if status:
        rows = [r for r in rows if r["status"] == status]
    return [
        {k: r.get(k) for k in ("id", "nummer", "datum", "empfaenger_name", "status", "summe_cent", "offen_cent",
                                "bezahlt_cent", "faellig_am", "ueberfaellig_tage", "bestellnummer")}
        for r in rows
    ]


def _w_uebersicht(db, user, a):
    return uebersicht.uebersicht(_int(a, "gewerbe_id"), _int(a, "jahr"), user, db)


def _w_anlagen(db, user, a):
    jahr = _int(a, "jahr", False)
    return [
        {k: x.get(k) for k in ("id", "bezeichnung", "anschaffungsdatum", "anschaffungskosten_cent", "nutzungsdauer_jahre",
                                "methode_text", "abgang_datum", "jahres_afa_cent", "restbuchwert_cent")}
        for x in afa.list_afa(_int(a, "gewerbe_id"), jahr, user, db)
    ]


def _w_fristen(db, user, a):
    f = fristen.liste(user, db)
    return {"heute": f["heute"], "fristen": [
        {k: x.get(k) for k in ("titel", "faellig_am", "tage_bis", "status", "erledigt_am")} for x in f["items"]
    ]}


def _w_belege(db, user, a):
    return [
        {k: b.get(k) for k in ("id", "original_name", "faellig_am", "created_at", "size_bytes")}
        for b in belege.list_belege(_int(a, "gewerbe_id"), "offen", user, db)
    ]


def _w_kategorien(db, user, a):
    return [
        {k: k_.get(k) for k in ("key", "name", "typ", "euer_zeile")}
        for k_ in kategorien.list_kategorien(_int(a, "jahr", False), db)
    ]


def _schema(props: dict, pflicht: list[str]) -> dict:
    return {"type": "object", "properties": props, "required": pflicht, "additionalProperties": False}


_GID = {"type": "integer", "description": "ID des Gewerbes (aus gewerbe_liste)"}
_JAHR = {"type": "integer", "description": "Steuerjahr, z. B. 2026"}

WERKZEUGE = [
    ("gewerbe_liste", "Alle Gewerbe (Firmen) des Kontos mit ID, Name, Steuernummer. Zuerst aufrufen.", _schema({}, []), _w_gewerbe),
    ("kennzahlen", "Einnahmen, Ausgaben (betrieblicher Teil), Umsatz nach § 19 und die Kleinunternehmer-Grenzen für ein Jahr.",
     _schema({"gewerbe_id": _GID, "jahr": _JAHR}, ["gewerbe_id", "jahr"]), _w_kennzahlen),
    ("euer_summenblatt", "EÜR-Summenblatt: Summen je Zeile der Anlage EÜR, Gewinn/Verlust. Kann fehlschlagen, wenn für das Jahr kein Mapping existiert.",
     _schema({"gewerbe_id": _GID, "jahr": _JAHR}, ["gewerbe_id", "jahr"]), _w_summenblatt),
    ("buchungen", "Buchungen eines Jahres (neueste zuerst) mit Positionen und Kategorien; optional Textsuche in Beschreibung/Kategorie.",
     _schema({"gewerbe_id": _GID, "jahr": _JAHR, "suche": {"type": "string", "description": "Suchtext (optional)"},
              "limit": {"type": "integer", "description": "höchstens so viele Buchungen, Standard 50, max. 200"}},
             ["gewerbe_id", "jahr"]), _w_buchungen),
    ("rechnungen", "Ausgangsrechnungen eines Jahres mit Status, Summe, offenem Rest und Fälligkeit; optional nach Status filtern (entwurf, versendet, bezahlt, storniert).",
     _schema({"gewerbe_id": _GID, "jahr": _JAHR, "status": {"type": "string"}}, ["gewerbe_id", "jahr"]), _w_rechnungen),
    ("uebersicht", "Was gerade wartet: Kennzahlen mit Vorjahr, offene Forderungen, überfällige Rechnungen, fällige Dauerbelege, offene Bankumsätze, Fristen, letzte Buchungen.",
     _schema({"gewerbe_id": _GID, "jahr": _JAHR}, ["gewerbe_id", "jahr"]), _w_uebersicht),
    ("anlagen", "Abschreibungen (Wirtschaftsgüter) mit Methode, Jahres-AfA und Restbuchwert.",
     _schema({"gewerbe_id": _GID, "jahr": {"type": "integer", "description": "für die Jahres-AfA (optional)"}}, ["gewerbe_id"]), _w_anlagen),
    ("fristen", "Steuerfristen des Kontos (Einkommensteuererklärung mit Anlage EÜR) mit Status.", _schema({}, []), _w_fristen),
    ("belege_eingang", "Noch nicht verbuchte Belege im Eingang (nur Metadaten, keine Dateiinhalte).",
     _schema({"gewerbe_id": _GID}, ["gewerbe_id"]), _w_belege),
    ("kategorien", "Buchungskategorien mit Typ (einnahme/ausgabe) und EÜR-Zeile für ein Jahr.",
     _schema({"jahr": _JAHR}, []), _w_kategorien),
]
_NACH_NAME = {n: (b, h) for n, b, _s, h in WERKZEUGE}


def _tools_liste() -> list[dict]:
    return [
        {"name": n, "description": beschr, "inputSchema": s, "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}}
        for n, beschr, s, _h in WERKZEUGE
    ]


def _aufrufen(db: sqlite3.Connection, user: dict, name: str, args) -> dict:
    if name not in _NACH_NAME:
        raise WerkzeugFehler(f"Unbekanntes Werkzeug „{name}“.")
    if not isinstance(args, dict):
        raise WerkzeugFehler("„arguments“ muss ein Objekt sein.")
    try:
        daten = _NACH_NAME[name][1](db, user, args)
    except HTTPException as e:
        raise WerkzeugFehler(str(e.detail))
    except WerkzeugFehler:
        raise
    except Exception:  # nichts nach außen geben, was Interna verrät
        log.exception("MCP-Werkzeug %s fehlgeschlagen", name)
        raise WerkzeugFehler("Das Werkzeug ist fehlgeschlagen.")
    text = json.dumps(daten, ensure_ascii=False, default=str)
    if len(text) > MAX_ZEICHEN:
        text = text[:MAX_ZEICHEN] + f'\n… [gekürzt auf {MAX_ZEICHEN} Zeichen — engere Abfrage (Jahr, Suche, limit) wählen]'
    return {"content": [{"type": "text", "text": text}], "isError": False}


# ── Anmeldung per Token, Bremse ─────────────────────────────────────────────

_zaehler: dict[int, list[float]] = {}
_lock = threading.Lock()


def _bremse(token_id: int) -> bool:
    jetzt = time.time()
    with _lock:
        spuren = [t for t in _zaehler.get(token_id, []) if t > jetzt - 60]
        spuren.append(jetzt)
        _zaehler[token_id] = spuren
    return len(spuren) <= ANFRAGEN_PRO_MINUTE


def _nicht_angemeldet(mit_token: bool = False) -> JSONResponse:
    # Der Verweis auf die Ressourcen-Metadaten (RFC 9728) ist der Einstieg für OAuth-Clients (Claude.ai & Co.).
    kopf = f'Bearer realm="vrwb_tab", resource_metadata="{oauth.metadaten_url()}"'
    if mit_token:
        kopf += ', error="invalid_token"'
    return JSONResponse(status_code=401, content={"detail": "Zugangs-Token fehlt oder ist ungültig."}, headers={"WWW-Authenticate": kopf})


def _antwort(id_, ergebnis=None, fehler=None) -> dict:
    return {"jsonrpc": "2.0", "id": id_, **({"error": fehler} if fehler else {"result": ergebnis})}


def _nachricht(db: sqlite3.Connection, user: dict, m) -> dict | None:
    if not isinstance(m, dict) or m.get("jsonrpc") != "2.0" or not isinstance(m.get("method"), str):
        return _antwort(m.get("id") if isinstance(m, dict) else None, fehler={"code": -32600, "message": "Ungültige Anfrage."})
    id_, methode, params = m.get("id"), m["method"], m.get("params") or {}
    if "id" not in m:  # Benachrichtigung (z. B. notifications/initialized): keine Antwort
        return None
    if methode == "initialize":
        wunsch = params.get("protocolVersion")
        return _antwort(id_, {
            "protocolVersion": wunsch if wunsch in PROTOKOLL_VERSIONEN else PROTOKOLL_VERSIONEN[0],
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "vrwb-tab", "title": "vrwb_tab Buchhaltung (nur lesen)", "version": "1.0.0"},
            "instructions": ANWEISUNG,
        })
    if methode == "ping":
        return _antwort(id_, {})
    if methode == "tools/list":
        return _antwort(id_, {"tools": _tools_liste()})
    if methode == "tools/call":
        try:
            return _antwort(id_, _aufrufen(db, user, str(params.get("name")), params.get("arguments") or {}))
        except WerkzeugFehler as e:
            return _antwort(id_, {"content": [{"type": "text", "text": str(e)}], "isError": True})
    return _antwort(id_, fehler={"code": -32601, "message": f"Methode „{methode}“ gibt es nicht."})


@router.post("/mcp")
async def mcp(request: Request):
    return await _mcp_sync(request)


async def _mcp_sync(request: Request):
    # Authentifizierung und Verarbeitung laufen in einem Thread (sqlite3 ist synchron).
    import anyio

    kopf = request.headers.get("authorization", "")
    body_bytes = await request.body()
    return await anyio.to_thread.run_sync(_verarbeiten, kopf, body_bytes)


def _verarbeiten(kopf: str, body_bytes: bytes):
    if not kopf.lower().startswith("bearer "):
        return _nicht_angemeldet()
    token = kopf[7:].strip()
    if not token.startswith((TOKEN_PREFIX, oauth.ACCESS_PREFIX)):
        return _nicht_angemeldet(bool(token))
    db = _connect()
    try:
        if token.startswith(TOKEN_PREFIX):
            row = db.execute("SELECT * FROM ki_token WHERE token_hash = ?", (_hash(token),)).fetchone()
            quelle, tabelle, bremse_id = "mcp", "ki_token", None
        else:  # OAuth-Zugriffs-Token (läuft nach einer Stunde ab, Refresh holt ein neues)
            row = db.execute("SELECT * FROM oauth_grant WHERE access_hash = ? AND access_expires > ?", (_hash(token), oauth._jetzt())).fetchone()
            quelle, tabelle, bremse_id = "oauth", "oauth_grant", None
        if row is None:
            return _nicht_angemeldet(True)
        bremse_id = row["id"] if quelle == "mcp" else -row["id"]
        owner = row["owner_email"].lower()
        # der Inhaber muss (noch) freigeschaltet sein, sonst gilt auch sein Token nicht mehr
        if not settings.OPEN_SIGNUP and not settings.is_email_allowed(owner):
            return _nicht_angemeldet()
        if not _bremse(bremse_id):
            return JSONResponse(status_code=429, content={"detail": "Zu viele Anfragen — bitte kurz warten."}, headers={"Retry-After": "30"})
        db.actor = f"{quelle}:{row['id']}"
        db.execute(f"UPDATE {tabelle} SET letzte_nutzung = datetime('now') WHERE id = ?", (row["id"],))
        db.commit()
        db.execute("PRAGMA query_only = ON")  # ab hier kann nichts mehr geschrieben werden
        user = {"email": owner, "name": row["name"] if quelle == "mcp" else "OAuth-App", "picture": None, "rolle": "assistent"}
        try:
            body = json.loads(body_bytes or b"")
        except (ValueError, UnicodeDecodeError):
            return JSONResponse(status_code=400, content=_antwort(None, fehler={"code": -32700, "message": "Kein gültiges JSON."}))
        if isinstance(body, list):
            antworten = [a for a in (_nachricht(db, user, m) for m in body[:20]) if a is not None]
            return JSONResponse(antworten) if antworten else Response(status_code=202)
        antwort = _nachricht(db, user, body)
        return JSONResponse(antwort) if antwort is not None else Response(status_code=202)
    finally:
        db.close()
