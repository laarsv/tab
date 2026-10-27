"""„Neuigkeiten gelesen" je Login. Die Einträge selbst leben im Frontend
(`lib/neuigkeiten.js`); hier wird nur gespeichert, welche IDs der Nutzer bestätigt hat —
damit das Fenster nicht auf jedem Gerät/Browser erneut aufpoppt."""
from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..auth.deps import get_current_user
from ..db import get_db

router = APIRouter(prefix="/api/news", tags=["news"])


class GelesenIn(BaseModel):
    ids: list[int] = Field(max_length=500)


def _gelesen(db: sqlite3.Connection, email: str) -> list[int]:
    rows = db.execute(
        "SELECT news_id FROM news_gelesen WHERE email = ? ORDER BY news_id", (email,)
    )
    return [r["news_id"] for r in rows]


@router.get("")
def news_status(user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    return {"gelesen": _gelesen(db, user["email"])}


@router.post("/gelesen")
def news_gelesen(
    body: GelesenIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    db.executemany(
        "INSERT OR IGNORE INTO news_gelesen (email, news_id) VALUES (?, ?)",
        [(user["email"], i) for i in set(body.ids) if i > 0],
    )
    db.commit()
    return {"gelesen": _gelesen(db, user["email"])}
