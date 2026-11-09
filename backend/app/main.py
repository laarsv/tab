"""Tab — schlanke EÜR-Buchhaltung für Kleinunternehmer (§19 UStG).

FastAPI + SQLite (eine Datei). Migrationen + idempotenter Seed laufen beim Start.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sqlite3
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import _connect, init_pragmas
from .migrations import run_migrations
from .routes import (
    abos,
    abschluss,
    afa,
    angebote,
    bank,
    berater,
    belege,
    buchungen,
    dauerbelege,
    einstellungen,
    export,
    fahrten,
    fristen,
    gewerbe,
    kategorien,
    kontakte,
    mahnwesen,
    mcp,
    meta,
    news,
    oauth,
    passkeys,
    rechnungen,
    uebersicht,
    vorlagen,
)
from .seed import seed
from .services.abo import run_faellige_abos
from .services.audit import SPERR_PRAEFIX, ensure_triggers
from .services.mail_import import run_mail_import
from .auth.berater_guard import berater_erlaubt
from .auth.router import router as auth_router
from .auth.session import decode_session

ABO_INTERVALL_SEKUNDEN = 6 * 3600
MAIL_IMPORT_INTERVALL_SEKUNDEN = 10 * 60


def _mit_connection(fn, actor: str) -> None:
    conn = _connect(actor=actor)  # Akteur fürs Änderungsprotokoll: system:<name>
    try:
        fn(conn)
    finally:
        conn.close()


async def _scheduler(name: str, fn, intervall: int) -> None:
    """Hintergrund-Lauf: beim Start und dann im Intervall (Abos, Mail-Import)."""
    while True:
        try:
            await asyncio.to_thread(_mit_connection, fn, f"system:{name}")
        except Exception:
            logging.getLogger(f"tab.{name}").exception("%s-Lauf fehlgeschlagen", name)
        await asyncio.sleep(intervall)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pragmas()
    os.makedirs(settings.UPLOAD_ROOT, exist_ok=True)
    conn = _connect(actor="system:start")
    try:
        run_migrations(conn)
        ensure_triggers(conn)  # Sperren, Änderungsprotokoll, Hash-Kette (services/audit.py)
        seed(conn)
    finally:
        conn.close()
    tasks = [
        asyncio.create_task(_scheduler("abo", run_faellige_abos, ABO_INTERVALL_SEKUNDEN)),
        asyncio.create_task(
            _scheduler("mail_import", run_mail_import, MAIL_IMPORT_INTERVALL_SEKUNDEN)
        ),
    ]
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(title="Tab", lifespan=lifespan)


@app.exception_handler(sqlite3.IntegrityError)
async def integritaet_fehler(request: Request, exc: sqlite3.IntegrityError):
    """Die Jahres-Sperre ist ein Datenbank-Trigger (RAISE) — hier wird sie zur lesbaren 409-Meldung.
    Alle anderen Integritätsfehler bleiben, was sie waren: ein 500."""
    text = str(exc)
    if text.startswith(SPERR_PRAEFIX):
        return JSONResponse(status_code=409, content={"detail": text.split(": ", 1)[1]})
    raise exc

@app.middleware("http")
async def steuerberatung_nur_lesen(request: Request, call_next):
    """Sitzungen der Steuerberatung dürfen nur die Abfragen aus auth/berater_guard.py — alles andere 403."""
    token = request.cookies.get(settings.COOKIE_NAME)
    payload = decode_session(token) if token else None
    if payload and payload.get("berater") and not berater_erlaubt(request.method, request.url.path):
        return JSONResponse(status_code=403, content={"detail": "Der Zugang für die Steuerberatung kann nur lesen."})
    return await call_next(request)


# OAuth-State (Authlib) läuft über die Starlette-Session (signiertes Cookie).
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET,
    https_only=settings.COOKIE_SECURE,
    same_site="lax",
)

if settings.cors_origins_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(auth_router)
app.include_router(gewerbe.router)
app.include_router(kategorien.router)
app.include_router(kontakte.router)
app.include_router(buchungen.router)
app.include_router(belege.router)
app.include_router(afa.router)
app.include_router(fahrten.router)
app.include_router(rechnungen.router)
app.include_router(abos.router)
app.include_router(mahnwesen.router)
app.include_router(fristen.router)
app.include_router(abschluss.router)
app.include_router(bank.router)
app.include_router(angebote.router)
app.include_router(dauerbelege.router)
app.include_router(uebersicht.router)
app.include_router(berater.router)
app.include_router(passkeys.router)
app.include_router(mcp.router)
app.include_router(oauth.router)
app.include_router(vorlagen.router)
app.include_router(einstellungen.router)
app.include_router(news.router)
app.include_router(export.router)
app.include_router(meta.router)
