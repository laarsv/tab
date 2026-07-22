"""Tab — schlanke EÜR-Buchhaltung für Kleinunternehmer (§19 UStG).

FastAPI + SQLite (eine Datei). Migrationen + idempotenter Seed laufen beim Start.
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import _connect, init_pragmas
from .migrations import run_migrations
from .routes import (
    abos,
    afa,
    belege,
    buchungen,
    einstellungen,
    export,
    fahrten,
    gewerbe,
    kategorien,
    meta,
    rechnungen,
)
from .seed import seed
from .services.abo import run_faellige_abos
from .auth.router import router as auth_router

ABO_INTERVALL_SEKUNDEN = 6 * 3600


def _abo_lauf() -> None:
    conn = _connect()
    try:
        run_faellige_abos(conn)
    finally:
        conn.close()


async def _abo_scheduler() -> None:
    """Wiederkehrende Rechnungen: beim Start und dann alle 6 h fällige Abos ausführen."""
    while True:
        try:
            await asyncio.to_thread(_abo_lauf)
        except Exception:
            logging.getLogger("tab.abo").exception("Abo-Lauf fehlgeschlagen")
        await asyncio.sleep(ABO_INTERVALL_SEKUNDEN)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pragmas()
    os.makedirs(settings.UPLOAD_ROOT, exist_ok=True)
    conn = _connect()
    try:
        run_migrations(conn)
        seed(conn)
    finally:
        conn.close()
    scheduler = asyncio.create_task(_abo_scheduler())
    yield
    scheduler.cancel()


app = FastAPI(title="Tab", lifespan=lifespan)

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
app.include_router(buchungen.router)
app.include_router(belege.router)
app.include_router(afa.router)
app.include_router(fahrten.router)
app.include_router(rechnungen.router)
app.include_router(abos.router)
app.include_router(einstellungen.router)
app.include_router(export.router)
app.include_router(meta.router)
