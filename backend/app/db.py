"""SQLite-Verbindung. Eine Datei, kein DB-Container. Eine Connection pro Request."""
from __future__ import annotations

import os
import sqlite3
from typing import Iterator

from .config import settings


def _connect() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(settings.DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(settings.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
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


def get_db() -> Iterator[sqlite3.Connection]:
    """FastAPI-Dependency: frische Connection pro Request, am Ende geschlossen."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()
