"""Tab — schlanke EÜR-Buchhaltung für Kleinunternehmer (§19 UStG).

FastAPI + SQLite (eine Datei). Migrationen + idempotenter Seed laufen beim Start.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .db import _connect, init_pragmas
from .migrations import run_migrations
from .routes import afa, belege, buchungen, export, gewerbe, kategorien, meta
from .seed import seed
from .auth.router import router as auth_router


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
    yield


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
app.include_router(export.router)
app.include_router(meta.router)
