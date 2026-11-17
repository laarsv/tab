"""Belege (Dateien). Workflow: erst in den EINGANG hochladen (ohne Kategorie),
später einer Buchung zuordnen. buchung_id NULL = offen/Eingang."""
from __future__ import annotations

import datetime as dt
import json
import os
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from ..auth.deps import check_gewerbe, get_current_user
from ..config import settings
from ..db import get_db
from ..services.beleg_extract import _kategorie_vorschlag, vorschlag_fuer_beleg
from ..services.beleg_scan import ScanAbgelehnt, bilder_zu_pdf
from ..services.beleg_store import BelegAbgelehnt, default_gewerbe_id, speichere_beleg

router = APIRouter(prefix="/api", tags=["belege"], dependencies=[Depends(get_current_user)])

def _valid_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, "faellig_am muss im Format YYYY-MM-DD sein.")
    return value


def _beleg_dict(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"],
        "gewerbe_id": r["gewerbe_id"],
        "buchung_id": r["buchung_id"],
        "original_name": r["original_name"],
        "content_type": r["content_type"],
        "size_bytes": r["size_bytes"],
        "created_at": r["created_at"],
        "faellig_am": r["faellig_am"],
        "offen": r["buchung_id"] is None,
        "eigenbeleg": json.loads(r["eigenbeleg"]) if r["eigenbeleg"] else None,
    }


def _check_beleg(db: sqlite3.Connection, user: dict, beleg_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Beleg nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    return row


@router.post("/belege", status_code=201)
def upload_beleg(
    file: UploadFile,
    gewerbe_id: int = Form(...),
    buchung_id: int | None = Form(None),
    faellig_am: str | None = Form(None),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    if faellig_am:
        _valid_date(faellig_am)
    check_gewerbe(db, user, gewerbe_id)
    if buchung_id is not None:
        b = db.execute("SELECT gewerbe_id FROM buchung WHERE id = ?", (buchung_id,)).fetchone()
        if b is None:
            raise HTTPException(404, "Buchung nicht gefunden.")
        if b["gewerbe_id"] != gewerbe_id:
            raise HTTPException(400, "Buchung gehört zu einem anderen Gewerbe.")

    try:
        beleg_id = speichere_beleg(
            db,
            gewerbe_id=gewerbe_id,
            original_name=file.filename or "",
            data=file.file.read(),
            content_type=file.content_type,
            faellig_am=faellig_am or None,
            buchung_id=buchung_id,
        )
    except BelegAbgelehnt as e:
        raise HTTPException(400, str(e))
    db.commit()
    return _beleg_dict(db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone())


@router.post("/belege/scan", status_code=201)
def scan_beleg(
    seiten: list[UploadFile],
    gewerbe_id: int = Form(...),
    buchung_id: int | None = Form(None),
    name: str | None = Form(None),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Belegscanner: fotografierte Seiten (im Browser aufbereitet) werden EINE PDF
    und landen wie ein Upload im Eingang (oder direkt an der Buchung)."""
    check_gewerbe(db, user, gewerbe_id)
    if buchung_id is not None:
        b = db.execute("SELECT gewerbe_id FROM buchung WHERE id = ?", (buchung_id,)).fetchone()
        if b is None:
            raise HTTPException(404, "Buchung nicht gefunden.")
        if b["gewerbe_id"] != gewerbe_id:
            raise HTTPException(400, "Buchung gehört zu einem anderen Gewerbe.")
    roh = []
    gesamt = 0
    grenze = settings.MAX_UPLOAD_MB * 1024 * 1024
    for f in seiten:
        data = f.file.read(grenze + 1)
        gesamt += len(data)
        if gesamt > grenze:
            raise HTTPException(400, f"Scan zu groß (max. {settings.MAX_UPLOAD_MB} MB).")
        roh.append(data)
    try:
        pdf = bilder_zu_pdf(roh)
    except ScanAbgelehnt as e:
        raise HTTPException(400, str(e))
    stempel = dt.datetime.now().strftime("%Y-%m-%d %H-%M")
    titel = "".join(c for c in (name or "").strip() if c not in '\\/:*?"<>|')[:80].strip()
    dateiname = f"{titel or 'Scan ' + stempel}.pdf"
    try:
        beleg_id = speichere_beleg(
            db,
            gewerbe_id=gewerbe_id,
            original_name=dateiname,
            data=pdf,
            content_type="application/pdf",
            buchung_id=buchung_id,
        )
    except BelegAbgelehnt as e:
        raise HTTPException(400, str(e))
    db.commit()
    out = _beleg_dict(db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone())
    out["seiten"] = len(roh)
    return out


@router.post("/belege/share", status_code=201)
def share_belege(
    belege: list[UploadFile],
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """PWA-Share-Target: vom Handy geteilte Dateien landen im Eingang des
    Standard-Gewerbes (Import-Gewerbe des Nutzers, sonst erstes aktives)."""
    gid = default_gewerbe_id(db, user["email"])
    if gid is None:
        raise HTTPException(400, "Kein aktives Gewerbe vorhanden.")
    gespeichert, fehler = [], []
    for f in belege:
        try:
            gespeichert.append(
                speichere_beleg(
                    db,
                    gewerbe_id=gid,
                    original_name=f.filename or "",
                    data=f.file.read(),
                    content_type=f.content_type,
                )
            )
        except BelegAbgelehnt as e:
            fehler.append(f"{f.filename}: {e}")
    db.commit()
    if not gespeichert and fehler:
        raise HTTPException(400, " · ".join(fehler))
    return {"gespeichert": len(gespeichert), "fehler": fehler, "gewerbe_id": gid}


@router.get("/belege")
def list_belege(
    gewerbe_id: int,
    status: str = "offen",  # offen | zugeordnet | all
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    sql = "SELECT * FROM beleg WHERE gewerbe_id = ?"
    if status == "offen":
        # Fällige zuerst (überfällig oben), dann Rest nach Upload-Zeit.
        sql += " AND buchung_id IS NULL ORDER BY faellig_am IS NULL, faellig_am, created_at DESC, id DESC"
    elif status == "zugeordnet":
        sql += " AND buchung_id IS NOT NULL ORDER BY created_at DESC, id DESC"
    else:
        sql += " ORDER BY created_at DESC, id DESC"
    return [_beleg_dict(r) for r in db.execute(sql, (gewerbe_id,))]


@router.get("/belege/eingang/count")
def eingang_count(
    gewerbe_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    n = db.execute(
        "SELECT COUNT(*) FROM beleg WHERE gewerbe_id = ? AND buchung_id IS NULL", (gewerbe_id,)
    ).fetchone()[0]
    return {"gewerbe_id": gewerbe_id, "offen": n}


@router.get("/buchungen/{buchung_id}/belege")
def list_buchung_belege(
    buchung_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    b = db.execute("SELECT gewerbe_id FROM buchung WHERE id = ?", (buchung_id,)).fetchone()
    if b is None:
        raise HTTPException(404, "Buchung nicht gefunden.")
    check_gewerbe(db, user, b["gewerbe_id"])
    rows = db.execute(
        "SELECT * FROM beleg WHERE buchung_id = ? ORDER BY id", (buchung_id,)
    ).fetchall()
    return [_beleg_dict(r) for r in rows]


class BelegPatch(BaseModel):
    buchung_id: int | None = None   # zuordnen; explizit null = zurück in den Eingang
    faellig_am: str | None = None   # explizit null = Fälligkeit entfernen
    gewerbe_id: int | None = None   # offenen Beleg in ein anderes eigenes Gewerbe verschieben


@router.patch("/belege/{beleg_id}")
def patch_beleg(
    beleg_id: int,
    body: BelegPatch,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    bel = _check_beleg(db, user, beleg_id)

    fields, values = [], []
    if "buchung_id" in body.model_fields_set:
        if body.buchung_id is not None:
            b = db.execute(
                "SELECT gewerbe_id FROM buchung WHERE id = ?", (body.buchung_id,)
            ).fetchone()
            if b is None:
                raise HTTPException(404, "Buchung nicht gefunden.")
            if b["gewerbe_id"] != bel["gewerbe_id"]:
                raise HTTPException(400, "Buchung gehört zu einem anderen Gewerbe.")
        fields.append("buchung_id = ?"); values.append(body.buchung_id)
    if "faellig_am" in body.model_fields_set:
        if body.faellig_am:
            _valid_date(body.faellig_am)
        fields.append("faellig_am = ?"); values.append(body.faellig_am or None)
    if body.gewerbe_id is not None and body.gewerbe_id != bel["gewerbe_id"]:
        if bel["buchung_id"] is not None:
            raise HTTPException(400, "Nur offene Eingangs-Belege können verschoben werden.")
        if bel["eigenbeleg"]:
            raise HTTPException(400, "Ein Eigenbeleg nennt sein Gewerbe als Aussteller — dort neu erstellen.")
        check_gewerbe(db, user, body.gewerbe_id)  # Ziel muss dem Nutzer gehören
        fields.append("gewerbe_id = ?"); values.append(body.gewerbe_id)
    if fields:
        db.execute(f"UPDATE beleg SET {', '.join(fields)} WHERE id = ?", (*values, beleg_id))
        db.commit()
    return _beleg_dict(db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone())


@router.get("/belege/{beleg_id}/vorschlag")
def beleg_vorschlag(
    beleg_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Beleg auslesen (E-Rechnung/PDF-Text/OCR) und Buchungsfelder vorschlagen —
    immer nur Vorschlag, das UI markiert die Werte zum Prüfen."""
    r = _check_beleg(db, user, beleg_id)
    path = os.path.join(settings.UPLOAD_ROOT, r["stored_name"])
    if not os.path.exists(path):
        raise HTTPException(410, "Datei nicht mehr vorhanden.")
    if r["eigenbeleg"]:  # Eigenbeleg: Angaben sind bekannt, nichts raten
        e = json.loads(r["eigenbeleg"])
        text = f"{e['empfaenger']} {e['gegenstand']}"
        return {"quelle": "eigenbeleg", "betrag_cent": e["betrag_cent"], "datum": e["datum"],
                "faellig_am": None, "lieferant": e["empfaenger"],
                "kategorie_id": _kategorie_vorschlag(db, r["gewerbe_id"], text, e["empfaenger"], "ausgabe"),
                "richtung": "ausgabe", "richtung_erkannt": True}
    try:
        return vorschlag_fuer_beleg(db, r, path)
    except Exception:
        # Erkennung darf nie das Verbuchen blockieren.
        return {"quelle": "keine", "betrag_cent": None, "datum": None,
                "faellig_am": None, "lieferant": None, "kategorie_id": None,
                "richtung": "ausgabe", "richtung_erkannt": False}


@router.get("/belege/{beleg_id}/download")
def download_beleg(
    beleg_id: int,
    inline: bool = False,  # inline=1 -> im Browser anzeigen (Vorschau) statt Download
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    r = _check_beleg(db, user, beleg_id)
    path = os.path.join(settings.UPLOAD_ROOT, r["stored_name"])
    if not os.path.exists(path):
        raise HTTPException(410, "Datei nicht mehr vorhanden.")
    return FileResponse(
        path,
        media_type=r["content_type"],
        filename=r["original_name"],
        content_disposition_type="inline" if inline else "attachment",
    )


@router.delete("/belege/{beleg_id}", status_code=204)
def delete_beleg(
    beleg_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    r = db.execute("SELECT * FROM beleg WHERE id = ?", (beleg_id,)).fetchone()
    if r is None:
        return
    check_gewerbe(db, user, r["gewerbe_id"])
    path = os.path.join(settings.UPLOAD_ROOT, r["stored_name"])
    # Erst den Datensatz löschen (die Jahres-Sperre kann ablehnen), dann die Datei — sonst wäre
    # bei einem abgelehnten Löschen die Datei eines abgeschlossenen Jahres schon weg.
    db.execute("DELETE FROM beleg WHERE id = ?", (beleg_id,))
    db.commit()
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
