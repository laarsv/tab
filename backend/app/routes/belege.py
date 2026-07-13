"""Belege (Dateien). Workflow: erst in den EINGANG hochladen (ohne Kategorie),
später einer Buchung zuordnen. buchung_id NULL = offen/Eingang."""
from __future__ import annotations

import os
import sqlite3
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..auth.deps import get_current_user
from ..config import settings
from ..db import get_db

router = APIRouter(prefix="/api", tags=["belege"], dependencies=[Depends(get_current_user)])

ALLOWED = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    # E-Rechnungen (XRechnung/ZUGFeRD-XML): empfangen + archivieren können ist
    # seit 2025 auch für Kleinunternehmer Pflicht — Anzeige/Parsing bewusst nicht.
    "application/xml": ".xml",
    "text/xml": ".xml",
}


def _beleg_dict(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "gewerbe_id": r["gewerbe_id"],
        "buchung_id": r["buchung_id"],
        "original_name": r["original_name"],
        "content_type": r["content_type"],
        "size_bytes": r["size_bytes"],
        "created_at": r["created_at"],
        "offen": r["buchung_id"] is None,
    }


@router.post("/belege", status_code=201)
def upload_beleg(
    file: UploadFile,
    gewerbe_id: int = Form(...),
    buchung_id: int | None = Form(None),
    db: sqlite3.Connection = Depends(get_db),
):
    if db.execute("SELECT 1 FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone() is None:
        raise HTTPException(404, "Gewerbe nicht gefunden.")
    if buchung_id is not None:
        b = db.execute("SELECT gewerbe_id FROM buchung WHERE id = ?", (buchung_id,)).fetchone()
        if b is None:
            raise HTTPException(404, "Buchung nicht gefunden.")
        if b["gewerbe_id"] != gewerbe_id:
            raise HTTPException(400, "Buchung gehört zu einem anderen Gewerbe.")

    ext = ALLOWED.get(file.content_type or "")
    if ext is None and (file.filename or "").lower().endswith(".xml"):
        ext = ".xml"  # Browser melden XML-Dateien teils ohne brauchbaren MIME-Typ
    if ext is None:
        raise HTTPException(400, "Nur PDF, JPG, PNG oder XML (E-Rechnung) erlaubt.")

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
        INSERT INTO beleg (gewerbe_id, buchung_id, original_name, stored_name, content_type, size_bytes)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (gewerbe_id, buchung_id, original, stored_name, file.content_type, len(data)),
    )
    db.commit()
    return _beleg_dict(db.execute("SELECT * FROM beleg WHERE id = ?", (cur.lastrowid,)).fetchone())


@router.get("/belege")
def list_belege(
    gewerbe_id: int,
    status: str = "offen",  # offen | zugeordnet | all
    db: sqlite3.Connection = Depends(get_db),
):
    sql = "SELECT * FROM beleg WHERE gewerbe_id = ?"
    if status == "offen":
        sql += " AND buchung_id IS NULL"
    elif status == "zugeordnet":
        sql += " AND buchung_id IS NOT NULL"
    sql += " ORDER BY created_at DESC, id DESC"
    return [_beleg_dict(r) for r in db.execute(sql, (gewerbe_id,))]


@router.get("/belege/eingang/count")
def eingang_count(gewerbe_id: int, db: sqlite3.Connection = Depends(get_db)):
    n = db.execute(
        "SELECT COUNT(*) FROM beleg WHERE gewerbe_id = ? AND buchung_id IS NULL", (gewerbe_id,)
    ).fetchone()[0]
    return {"gewerbe_id": gewerbe_id, "offen": n}


@router.get("/buchungen/{buchung_id}/belege")
def list_buchung_belege(buchung_id: int, db: sqlite3.Connection = Depends(get_db)):
    rows = db.execute(
        "SELECT * FROM beleg WHERE buchung_id = ? ORDER BY id", (buchung_id,)
    ).fetchall()
    return [_beleg_dict(r) for r in rows]


class BelegPatch(BaseModel):
    buchung_id: int | None = None  # zuordnen; explizit null = zurück in den Eingang


@router.patch("/belege/{beleg_id}")
def patch_beleg(beleg_id: int, body: BelegPatch, db: sqlite3.Connection = Depends(get_db)):
    bel = db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone()
    if bel is None:
        raise HTTPException(404, "Beleg nicht gefunden.")
    if body.buchung_id is not None:
        b = db.execute("SELECT gewerbe_id FROM buchung WHERE id = ?", (body.buchung_id,)).fetchone()
        if b is None:
            raise HTTPException(404, "Buchung nicht gefunden.")
        if b["gewerbe_id"] != bel["gewerbe_id"]:
            raise HTTPException(400, "Buchung gehört zu einem anderen Gewerbe.")
    db.execute("UPDATE beleg SET buchung_id = ? WHERE id = ?", (body.buchung_id, beleg_id))
    db.commit()
    return _beleg_dict(db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone())


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
