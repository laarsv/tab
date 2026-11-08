"""SQLite-Verbindung. Eine Datei, kein DB-Container. Eine Connection pro Request."""
from __future__ import annotations

import hashlib
import os
import sqlite3
from typing import Iterator

from fastapi import Request

from .config import settings


class TabConnection(sqlite3.Connection):
    """Verbindung mit „Akteur“ für das Änderungsprotokoll (services/audit.py): die Trigger
    fragen über die SQL-Funktion tab_actor() ab, wer gerade schreibt (E-Mail des angemeldeten
    Nutzers, bei Hintergrundläufen „system:<name>“)."""

    actor: str | None = None


def _sha256(text: str | None) -> str | None:
    return None if text is None else hashlib.sha256(str(text).encode("utf-8")).hexdigest()


def _connect(actor: str | None = None) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(settings.DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False, factory=TabConnection)
    conn.row_factory = sqlite3.Row
    conn.actor = actor
    # SQL-Funktionen für die Protokoll-Trigger (Hash-Kette, Akteur). Fehlen sie auf einer
    # Verbindung (z. B. sqlite3-Kommandozeile), scheitern Schreibzugriffe auf geschützte
    # Tabellen — gewollt: nichts wird unprotokolliert geändert.
    conn.create_function("tab_sha256", 1, _sha256, deterministic=True)
    conn.create_function("tab_actor", 0, lambda: conn.actor)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def init_pragmas() -> None:
    """Einmalig beim Start: WAL aktivieren (persistiert in der DB-Datei)."""
    conn = _connect()
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    finally:
        conn.close()


def _akteur(request: Request) -> str | None:
    """E-Mail aus dem Session-Cookie — nur fürs Protokoll; die Zugriffsprüfung macht
    get_current_user."""
    from .auth.session import decode_session  # lokal: vermeidet Importzyklus

    token = request.cookies.get(settings.COOKIE_NAME)
    payload = decode_session(token) if token else None
    email = (payload or {}).get("email")
    return email.lower() if email else None


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """FastAPI-Dependency: frische Connection pro Request, am Ende geschlossen."""
    conn = _connect(actor=_akteur(request))
    try:
        yield conn
    finally:
        conn.close()
