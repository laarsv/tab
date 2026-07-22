"""Buchungen CRUD. Eine Buchung = ein Vorgang/Beleg-Kopf mit 1..n Positionen
(je Position eine Kategorie + Betrag). Belege (Dateien) hängen separat (routes/belege.py)
und können beim Anlegen via beleg_ids aus dem Eingang verknüpft werden. AfA: /api/afa."""
from __future__ import annotations

import csv
import datetime as dt
import io
import sqlite3

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db

router = APIRouter(
    prefix="/api/buchungen", tags=["buchungen"], dependencies=[Depends(get_current_user)]
)


def _valid_date(value: str) -> str:
    try:
        dt.date.fromisoformat(value)
    except ValueError:
        raise ValueError("datum muss im Format YYYY-MM-DD sein.")
    return value


class PositionIn(BaseModel):
    kategorie_id: int
    betrag_cent: int = Field(gt=0)
    beleg_details: str | None = None


class BuchungIn(BaseModel):
    gewerbe_id: int
    datum: str
    beschreibung: str | None = None
    positionen: list[PositionIn] = Field(min_length=1)
    beleg_ids: list[int] = Field(default_factory=list)  # Eingangs-Belege verknüpfen

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str) -> str:
        return _valid_date(v)


class BuchungPatch(BaseModel):
    datum: str | None = None
    beschreibung: str | None = None
    positionen: list[PositionIn] | None = None  # wenn gesetzt: ersetzt alle Positionen

    @field_validator("datum")
    @classmethod
    def _v_date(cls, v: str | None) -> str | None:
        return _valid_date(v) if v is not None else v


def _check_position(db: sqlite3.Connection, pos: PositionIn) -> None:
    k = db.execute("SELECT * FROM kategorie WHERE id = ?", (pos.kategorie_id,)).fetchone()
    if k is None:
        raise HTTPException(404, "Kategorie nicht gefunden.")
    if k["ist_afa"]:
        raise HTTPException(400, "AfA-Kategorien bitte über die AfA-Erfassung anlegen.")
    if k["belegpflicht_extra"] and not (pos.beleg_details and pos.beleg_details.strip()):
        raise HTTPException(400, f"Für „{k['name']}“ sind Beleg-Details Pflicht.")


def _check_buchung(db: sqlite3.Connection, user: dict, buchung_id: int) -> sqlite3.Row:
    row = db.execute("SELECT * FROM buchung WHERE id = ?", (buchung_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Buchung nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    return row


def _positionen(db: sqlite3.Connection, buchung_id: int) -> list[dict]:
    rows = db.execute(
        """
        SELECT p.*, k.name AS kategorie_name, k.typ AS kategorie_typ,
               k.belegpflicht_extra, k.abzug_quote
        FROM buchung_position p JOIN kategorie k ON k.id = p.kategorie_id
        WHERE p.buchung_id = ? ORDER BY p.id
        """,
        (buchung_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def _row(db: sqlite3.Connection, buchung_id: int) -> dict:
    h = db.execute(
        """
        SELECT b.*,
               (SELECT COUNT(*) FROM beleg WHERE beleg.buchung_id = b.id) AS beleg_count,
               (SELECT COALESCE(SUM(betrag_cent),0) FROM buchung_position WHERE buchung_id = b.id) AS summe_cent
        FROM buchung b WHERE b.id = ?
        """,
        (buchung_id,),
    ).fetchone()
    d = dict(h)
    d["positionen"] = _positionen(db, buchung_id)
    return d


@router.get("")
def list_buchungen(
    gewerbe_id: int,
    jahr: int | None = None,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    sql = (
        "SELECT b.id, b.gewerbe_id, b.datum, b.beschreibung, b.created_at, b.updated_at, "
        "(SELECT COUNT(*) FROM beleg WHERE beleg.buchung_id = b.id) AS beleg_count, "
        "(SELECT COALESCE(SUM(betrag_cent),0) FROM buchung_position WHERE buchung_id = b.id) AS summe_cent "
        "FROM buchung b WHERE b.gewerbe_id = ?"
    )
    params: list = [gewerbe_id]
    if jahr is not None:
        sql += " AND substr(b.datum,1,4) = ?"
        params.append(str(jahr))
    sql += " ORDER BY b.datum DESC, b.id DESC"

    heads = [dict(r) for r in db.execute(sql, params)]
    if not heads:
        return []
    ids = [h["id"] for h in heads]
    qmarks = ",".join("?" * len(ids))
    pos_rows = db.execute(
        f"""
        SELECT p.*, k.name AS kategorie_name, k.typ AS kategorie_typ,
               k.belegpflicht_extra, k.abzug_quote
        FROM buchung_position p JOIN kategorie k ON k.id = p.kategorie_id
        WHERE p.buchung_id IN ({qmarks}) ORDER BY p.id
        """,
        ids,
    ).fetchall()
    by_buchung: dict[int, list] = {i: [] for i in ids}
    for r in pos_rows:
        by_buchung[r["buchung_id"]].append(dict(r))
    for h in heads:
        h["positionen"] = by_buchung[h["id"]]
    return heads


@router.post("", status_code=201)
def create_buchung(
    body: BuchungIn,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, body.gewerbe_id)
    for pos in body.positionen:
        _check_position(db, pos)

    # Eingangs-Belege prüfen (müssen zum Gewerbe gehören und noch offen sein)
    for bid in body.beleg_ids:
        bel = db.execute("SELECT * FROM beleg WHERE id = ?", (bid,)).fetchone()
        if bel is None:
            raise HTTPException(404, f"Beleg {bid} nicht gefunden.")
        if bel["gewerbe_id"] != body.gewerbe_id:
            raise HTTPException(400, "Beleg gehört zu einem anderen Gewerbe.")

    cur = db.execute(
        "INSERT INTO buchung (gewerbe_id, datum, beschreibung) VALUES (?, ?, ?)",
        (body.gewerbe_id, body.datum, (body.beschreibung or "").strip() or None),
    )
    buchung_id = cur.lastrowid
    db.executemany(
        "INSERT INTO buchung_position (buchung_id, kategorie_id, betrag_cent, beleg_details) "
        "VALUES (?, ?, ?, ?)",
        [
            (buchung_id, p.kategorie_id, p.betrag_cent, (p.beleg_details or "").strip() or None)
            for p in body.positionen
        ],
    )
    for bid in body.beleg_ids:
        db.execute("UPDATE beleg SET buchung_id = ? WHERE id = ?", (buchung_id, bid))
    db.commit()
    return _row(db, buchung_id)


@router.patch("/{buchung_id}")
def update_buchung(
    buchung_id: int,
    body: BuchungPatch,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    _check_buchung(db, user, buchung_id)

    fields, values = [], []
    if body.datum is not None:
        fields.append("datum = ?"); values.append(body.datum)
    if body.beschreibung is not None:
        fields.append("beschreibung = ?"); values.append(body.beschreibung.strip() or None)
    if fields:
        fields.append("updated_at = datetime('now')")
        db.execute(f"UPDATE buchung SET {', '.join(fields)} WHERE id = ?", (*values, buchung_id))

    if body.positionen is not None:
        if len(body.positionen) == 0:
            raise HTTPException(400, "Mindestens eine Position ist nötig.")
        for pos in body.positionen:
            _check_position(db, pos)
        db.execute("DELETE FROM buchung_position WHERE buchung_id = ?", (buchung_id,))
        db.executemany(
            "INSERT INTO buchung_position (buchung_id, kategorie_id, betrag_cent, beleg_details) "
            "VALUES (?, ?, ?, ?)",
            [
                (buchung_id, p.kategorie_id, p.betrag_cent, (p.beleg_details or "").strip() or None)
                for p in body.positionen
            ],
        )
    db.commit()
    return _row(db, buchung_id)


@router.delete("/{buchung_id}", status_code=204)
def delete_buchung(
    buchung_id: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    # Positionen via ON DELETE CASCADE, Belege fallen via ON DELETE SET NULL zurück in den Eingang.
    _check_buchung(db, user, buchung_id)
    db.execute("DELETE FROM buchung WHERE id = ?", (buchung_id,))
    db.commit()


# ── CSV-Import (einmalige Übernahme aus der alten Excel-Liste) ──────────────────
# Semikolon-CSV, Spalten: Datum;Betrag;Kategorie[;Beschreibung[;Beleg-Details]].
# Datum TT.MM.JJJJ oder JJJJ-MM-TT, Betrag deutsch (1.234,56), Kategorie = Key oder Name.
# Alles-oder-nichts: bei Fehlern wird nichts angelegt, die Fehlerliste kommt als 400.


def _parse_import_datum(raw: str) -> str | None:
    s = raw.strip()
    try:
        if "." in s:
            return dt.datetime.strptime(s, "%d.%m.%Y").date().isoformat()
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        return None


def _parse_import_betrag_cent(raw: str) -> int | None:
    s = raw.strip().replace("€", "").replace(" ", "")
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        cent = round(float(s) * 100)
    except ValueError:
        return None
    return cent if cent > 0 else None


@router.post("/import", status_code=201)
def import_csv(
    file: UploadFile,
    gewerbe_id: int = Form(...),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)

    try:
        text = file.file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, "Datei muss UTF-8-kodiert sein.")

    kat_lookup: dict[str, sqlite3.Row] = {}
    for k in db.execute("SELECT * FROM kategorie WHERE aktiv = 1"):
        kat_lookup[k["key"].lower()] = k
        kat_lookup[k["name"].lower()] = k

    zeilen = [z for z in csv.reader(io.StringIO(text), delimiter=";") if any(c.strip() for c in z)]
    if zeilen and zeilen[0] and "datum" in zeilen[0][0].strip().lower():
        zeilen = zeilen[1:]  # Kopfzeile überspringen
    if not zeilen:
        raise HTTPException(400, "Keine Datenzeilen gefunden.")

    fehler: list[str] = []
    parsed: list[tuple[str, int, sqlite3.Row, str | None, str | None]] = []
    for i, z in enumerate(zeilen, start=1):
        if len(z) < 3:
            fehler.append(f"Zeile {i}: erwartet Datum;Betrag;Kategorie (mind. 3 Spalten).")
            continue
        datum = _parse_import_datum(z[0])
        betrag = _parse_import_betrag_cent(z[1])
        kat = kat_lookup.get(z[2].strip().lower())
        beschreibung = z[3].strip() if len(z) > 3 and z[3].strip() else None
        details = z[4].strip() if len(z) > 4 and z[4].strip() else None
        if datum is None:
            fehler.append(f"Zeile {i}: ungültiges Datum „{z[0].strip()}“ (TT.MM.JJJJ oder JJJJ-MM-TT).")
        if betrag is None:
            fehler.append(f"Zeile {i}: ungültiger Betrag „{z[1].strip()}“ (positiv, z. B. 12,34).")
        if kat is None:
            fehler.append(f"Zeile {i}: unbekannte Kategorie „{z[2].strip()}“ (Key oder Name).")
        elif kat["ist_afa"]:
            fehler.append(f"Zeile {i}: AfA-Kategorien bitte über die AfA-Erfassung anlegen.")
        elif kat["belegpflicht_extra"] and not details:
            fehler.append(f"Zeile {i}: für „{kat['name']}“ sind Beleg-Details Pflicht (5. Spalte).")
        if datum and betrag and kat and not kat["ist_afa"] and not (kat["belegpflicht_extra"] and not details):
            parsed.append((datum, betrag, kat, beschreibung, details))

    if fehler:
        raise HTTPException(400, "Import abgebrochen — nichts angelegt:\n" + "\n".join(fehler[:20]))

    for datum, betrag, kat, beschreibung, details in parsed:
        cur = db.execute(
            "INSERT INTO buchung (gewerbe_id, datum, beschreibung) VALUES (?, ?, ?)",
            (gewerbe_id, datum, beschreibung),
        )
        db.execute(
            "INSERT INTO buchung_position (buchung_id, kategorie_id, betrag_cent, beleg_details) "
            "VALUES (?, ?, ?, ?)",
            (cur.lastrowid, kat["id"], betrag, details),
        )
    db.commit()
    return {"angelegt": len(parsed)}
