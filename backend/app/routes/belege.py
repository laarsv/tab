"""Beleg-Dateien (PDF/Bild) je Buchung: Upload, Liste, Download, Löschen."""
from __future__ import annotations

import os
import sqlite3
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..auth.deps import get_current_user
from ..config import settings
from ..db import get_db

router = APIRouter(prefix="/api", tags=["belege"], dependencies=[Depends(get_current_user)])

ALLOWED = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


def _beleg_dict(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "buchung_id": r["buchung_id"],
        "original_name": r["original_name"],
        "content_type": r["content_type"],
        "size_bytes": r["size_bytes"],
        "created_at": r["created_at"],
    }


@router.get("/buchungen/{buchung_id}/belege")
def list_belege(buchung_id: int, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM beleg WHERE buchung_id = ? ORDER BY id", (buchung_id,)
    ).fetchall()
    return [_beleg_dict(r) for r in rows]


@router.post("/buchungen/{buchung_id}/belege", status_code=201)
def upload_beleg(buchung_id: int, file: UploadFile, db: sqlite3.Connection = Depends(get_db)):
    if db.execute("SELECT 1 FROM buchung WHERE id = ?", (buchung_id,)).fetchone() is None:
        raise HTTPException(404, "Buchung nicht gefunden.")

    ext = ALLOWED.get(file.content_type or "")
    if ext is None:
        raise HTTPException(400, "Nur PDF, JPG oder PNG erlaubt.")

    data = file.file.read()
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(data) == 0:
        raise HTTPException(400, "Datei ist leer.")
    if len(data) > max_bytes:
        raise HTTPException(400, f"Datei zu groß (max. {settings.MAX_UPLOAD_MB} MB).")

    stored_name = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(settings.UPLOAD_ROOT, exist_ok=True)
    with open(os.path.join(settings.UPLOAD_ROOT, stored_name), "wb") as fh:
        fh.write(data)

    original = os.path.basename(file.filename or f"beleg{ext}")
    cur = db.execute(
        """
        INSERT INTO beleg (buchung_id, original_name, stored_name, content_type, size_bytes)
        VALUES (?, ?, ?, ?, ?)
        """,
        (buchung_id, original, stored_name, file.content_type, len(data)),
    )
    db.commit()
    return _beleg_dict(db.execute("SELECT * FROM beleg WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.get("/belege/{beleg_id}/download")
def download_beleg(beleg_id: int, db: sqlite3.Connection = Depends(get_db)):
    r = db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone()
    if r is None:
        raise HTTPException(404, "Beleg nicht gefunden.")
    path = os.path.join(settings.UPLOAD_ROOT, r["stored_name"])
    if not os.path.exists(path):
        raise HTTPException(410, "Datei nicht mehr vorhanden.")
    return FileResponse(path, media_type=r["content_type"], filename=r["original_name"])


@router.delete("/belege/{beleg_id}", status_code=204)
def delete_beleg(beleg_id: int, db: sqlite3.Connection = Depends(get_db)):
    r = db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone()
    if r is None:
        return
    path = os.path.join(settings.UPLOAD_ROOT, r["stored_name"])
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
    db.execute("DELETE FROM beleg WHERE id = ?", (beleg_id,))
    db.commit()
