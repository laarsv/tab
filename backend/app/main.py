"""Tab — schlanke EÜR-Buchhaltung für Kleinunternehmer (§19 UStG).

FastAPI + SQLite (eine Datei). Migrationen + idempotenter Seed laufen beim Start.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import _connect, init_pragmas
from .migrations import run_migrations
from .routes import afa, buchungen, export, gewerbe, kategorien, meta
from .seed import seed
from .auth.router import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_pragmas()
    conn = _connect()
    try:
        run_migrations(conn)
        seed(conn)
    finally:
        conn.close()
    yield


app = FastAPI(title="Tab", lifespan=lifespan)

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
app.include_router(afa.router)
app.include_router(export.router)
app.include_router(meta.router)
