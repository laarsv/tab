"""Bank: Kontoauszug-Import (CAMT.053/CSV/PDF), Bankabruf (Enable Banking, unten), Umsatzliste, Zuordnungsvorschläge.

Zugeordnet wird über das normale Buchungs-Fenster (BuchungModal, vorbelegt) —
`POST /api/buchungen` mit `bank_umsatz_id` verknüpft den Umsatz in derselben Transaktion
(und markiert bei `rechnung_id` die Rechnung als bezahlt). Hier: Konten, Import, Liste,
Vorschläge, Ignorieren/Wieder öffnen.
"""
from __future__ import annotations

import json
import logging
import sqlite3

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services import auto_zuordnung as auto
from ..services import bank_abruf as abruf
from ..services import bank_import as imp
from ..services import bank_match as match
from ..services.girocode import iban_gueltig, iban_normal

router = APIRouter(prefix="/api/bank", tags=["bank"])


def _konto(db: sqlite3.Connection, user: dict, konto_id: int) -> sqlite3.Row:
    k = db.execute("SELECT * FROM bankkonto WHERE id = ?", (konto_id,)).fetchone()
    if k is None:
        raise HTTPException(404, "Konto nicht gefunden.")
    check_gewerbe(db, user, k["gewerbe_id"])
    return k


def _umsatz(db: sqlite3.Connection, user: dict, umsatz_id: int) -> dict:
    u = db.execute("SELECT * FROM bank_umsatz WHERE id = ?", (umsatz_id,)).fetchone()
    if u is None:
        raise HTTPException(404, "Umsatz nicht gefunden.")
    check_gewerbe(db, user, u["gewerbe_id"])
    return dict(u)


def _status(u: dict) -> str:
    return "zugeordnet" if u["buchung_id"] is not None else u["status"]


# ── Konten ──────────────────────────────────────────────────────────────────

@router.get("/konten")
def konten(gewerbe_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, gewerbe_id)
    rows = db.execute(
        """
        SELECT k.*,
          (SELECT COUNT(*) FROM bank_umsatz u WHERE u.konto_id = k.id AND u.buchung_id IS NULL AND u.status = 'offen') AS offen,
          (SELECT COUNT(*) FROM bank_umsatz u WHERE u.konto_id = k.id) AS gesamt,
          (SELECT MAX(bis) FROM bank_import i WHERE i.konto_id = k.id) AS letzter_umsatz
        FROM bankkonto k WHERE k.gewerbe_id = ? ORDER BY k.name COLLATE NOCASE
        """,
        (gewerbe_id,),
    ).fetchall()
    return [dict(r) for r in rows]


class KontoIn(BaseModel):
    gewerbe_id: int
    name: str = Field(min_length=1, max_length=80)
    iban: str | None = Field(default=None, max_length=40)


@router.post("/konten", status_code=201)
def konto_anlegen(body: KontoIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    iban = iban_normal(body.iban) if body.iban and body.iban.strip() else None
    if iban and not iban_gueltig(iban):
        raise HTTPException(400, "Die IBAN ist ungültig (Prüfziffer stimmt nicht).")
    try:
        cur = db.execute(
            "INSERT INTO bankkonto (gewerbe_id, name, iban) VALUES (?, ?, ?)", (body.gewerbe_id, body.name.strip(), iban)
        )
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Ein Konto mit dieser IBAN gibt es schon.")
    db.commit()
    return dict(db.execute("SELECT * FROM bankkonto WHERE id = ?", (cur.lastrowid,)).fetchone())


class KontoPatch(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.patch("/konten/{konto_id}")
def konto_umbenennen(
    konto_id: int, body: KontoPatch, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    _konto(db, user, konto_id)
    db.execute("UPDATE bankkonto SET name = ? WHERE id = ?", (body.name.strip(), konto_id))
    db.commit()
    return dict(db.execute("SELECT * FROM bankkonto WHERE id = ?", (konto_id,)).fetchone())


# ── Import ──────────────────────────────────────────────────────────────────

def _mapping(text: str | None) -> dict | None:
    if not text:
        return None
    try:
        m = json.loads(text)
    except ValueError:
        raise HTTPException(400, "Die Spaltenzuordnung ist kein gültiges JSON.")
    if not isinstance(m, dict):
        raise HTTPException(400, "Die Spaltenzuordnung ist ungültig.")
    return m


def _beispiel(u: imp.Umsatz) -> dict:
    return {
        "datum": u.datum, "betrag_cent": u.betrag_cent, "gegenpartei": u.gegenpartei,
        "verwendungszweck": u.verwendungszweck,
    }


@router.post("/import/vorschau")
def import_vorschau(
    file: UploadFile = File(...),
    gewerbe_id: int = Form(...),
    mapping: str | None = Form(None),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    """Datei lesen, nichts speichern: Format, Konto, Zeitraum, erste Umsätze und bei CSV die
    (geratene oder gewählte) Spaltenzuordnung. Bei unvollständiger CSV-Zuordnung kommt `fehler`
    zusammen mit den Spalten zurück, damit das UI sie korrigieren lässt."""
    check_gewerbe(db, user, gewerbe_id)
    data = file.file.read(imp.MAX_BYTES + 1)
    antwort: dict = {"dateiname": file.filename}
    try:
        erg, info = imp.lesen(data, file.filename or "", _mapping(mapping))
    except imp.BankImportError as e:
        if imp.format_erkennen(data, file.filename or "") != "csv":
            raise HTTPException(400, str(e))
        try:
            c = imp.csv_einlesen(data)
        except imp.BankImportError as e2:
            raise HTTPException(400, str(e2))
        return {
            **antwort, "format": "csv", "fehler": str(e),
            "csv": {"header": c["header"], "mapping": imp.mapping_raten(c["header"]), "trenner": c["trenner"]},
        }
    konto = None
    if erg.iban:
        k = db.execute("SELECT id, name FROM bankkonto WHERE gewerbe_id = ? AND iban = ?", (gewerbe_id, erg.iban)).fetchone()
        konto = dict(k) if k else None
    daten = sorted(u.datum for u in erg.umsaetze) or [erg.zeitraum_von, erg.zeitraum_bis]
    fps = imp.fingerprints(erg.umsaetze)
    schon = 0
    if konto:
        schon = sum(
            1 for fp in fps
            if db.execute("SELECT 1 FROM bank_umsatz WHERE konto_id = ? AND fingerprint = ?", (konto["id"], fp)).fetchone()
        )
    return {
        **antwort, "format": erg.format, "iban": erg.iban, "kontoname": erg.kontoname, "konto": konto,
        "anzahl": len(erg.umsaetze), "schon_vorhanden": schon, "von": daten[0], "bis": daten[-1],
        "saldo_pruefung": imp._saldo_pruefung(erg), "warnungen": erg.warnungen,
        "beispiele": [_beispiel(u) for u in erg.umsaetze[:5]],
        "csv": {"header": info["header"], "mapping": info["mapping"], "trenner": info["trenner"]} if info else None,
        "fehler": None,
    }


@router.post("/import", status_code=201)
def import_ausfuehren(
    file: UploadFile = File(...),
    gewerbe_id: int = Form(...),
    konto_id: int | None = Form(None),
    mapping: str | None = Form(None),
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    data = file.file.read(imp.MAX_BYTES + 1)
    try:
        ergebnis = imp.importiere(
            db, gewerbe_id=gewerbe_id, konto_id=konto_id, dateiname=file.filename or "", data=data,
            mapping=_mapping(mapping), email=user["email"],
        )
    except imp.BankImportError as e:
        db.rollback()
        raise HTTPException(400, str(e))
    # Gleich danach eindeutige Treffer zuordnen (ohne Fotos: Texterkennung dauert; die holt der Stundenlauf)
    try:
        ergebnis["automatisch"] = auto.lauf(db, gewerbe_id, user, bilder=False)
    except Exception:
        db.rollback()
        logging.getLogger("tab.auto_zuordnung").exception("Auto-Zuordnung nach dem Import fehlgeschlagen")
        ergebnis["automatisch"] = None
    return ergebnis


# ── Umsatzliste ─────────────────────────────────────────────────────────────

def _liste_dict(u: sqlite3.Row, hinweis: dict | None, buchung: sqlite3.Row | None) -> dict:
    d = dict(u)
    d["status_effektiv"] = _status(d)
    d["rechnung_hinweis"] = hinweis
    d["buchung"] = (
        {"id": buchung["id"], "datum": buchung["datum"], "beschreibung": buchung["beschreibung"]} if buchung else None
    )
    return d


@router.get("/umsaetze")
def umsaetze(
    gewerbe_id: int,
    konto_id: int | None = None,
    filter: str = "offen",
    q: str | None = None,
    limit: int = 300,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    if filter not in ("offen", "alle", "zugeordnet", "ignoriert"):
        raise HTTPException(400, "Unbekannter Filter.")
    where, args = ["u.gewerbe_id = ?"], [gewerbe_id]
    if konto_id is not None:
        where.append("u.konto_id = ?")
        args.append(konto_id)
    scope = " AND ".join(where)
    scope_args = list(args)
    stat = {
        "offen": "u.buchung_id IS NULL AND u.status = 'offen'",
        "zugeordnet": "u.buchung_id IS NOT NULL",
        "ignoriert": "u.buchung_id IS NULL AND u.status = 'ignoriert'",
    }
    if filter != "alle":
        where.append(stat[filter])
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        where.append(
            "(lower(COALESCE(u.gegenpartei,'') || ' ' || COALESCE(u.verwendungszweck,'')) LIKE ? "
            "OR replace(printf('%.2f', abs(u.betrag_cent) / 100.0), '.', ',') LIKE ?)"
        )
        args += [like, like]
    rows = db.execute(
        f"SELECT u.* FROM bank_umsatz u WHERE {' AND '.join(where)} ORDER BY u.datum DESC, u.id DESC LIMIT ?",
        (*args, max(1, min(limit, 500))),
    ).fetchall()
    offen_rechnungen = match.offene_rechnungen(db, gewerbe_id)
    ergebnis = []
    for u in rows:
        hinweis = None
        if u["buchung_id"] is None and u["status"] == "offen" and u["betrag_cent"] > 0:
            t = match.rechnung_treffer(offen_rechnungen, dict(u))
            if t:
                hinweis = {"id": t[0]["id"], "nummer": t[0]["nummer"], "punkte": t[0]["punkte"]}
        buchung = (
            db.execute("SELECT id, datum, beschreibung FROM buchung WHERE id = ?", (u["buchung_id"],)).fetchone()
            if u["buchung_id"] else None
        )
        ergebnis.append(_liste_dict(u, hinweis, buchung))
    s = db.execute(
        f"SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN u.betrag_cent > 0 THEN u.betrag_cent END), 0) AS ein, "
        f"COALESCE(SUM(CASE WHEN u.betrag_cent < 0 THEN -u.betrag_cent END), 0) AS aus FROM bank_umsatz u "
        f"WHERE {scope} AND {stat['offen']}",
        scope_args,
    ).fetchone()
    g = db.execute("SELECT bank_auto FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    return {
        "umsaetze": ergebnis,
        "offen": {"anzahl": s["n"], "eingaenge_cent": s["ein"], "ausgaenge_cent": s["aus"]},
        "automatik": bool(g["bank_auto"]) if g else False,
    }


@router.get("/umsaetze/{umsatz_id}/vorschlaege")
def vorschlaege(umsatz_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    u = _umsatz(db, user, umsatz_id)
    offen = match.offene_rechnungen(db, u["gewerbe_id"])
    treffer = match.rechnung_treffer(offen, u) if u["betrag_cent"] > 0 else []
    ids = {t["id"] for t in treffer}
    return {
        "umsatz": {**u, "status_effektiv": _status(u)},
        "rechnungen": treffer,
        "weitere_rechnungen": [r for r in offen if r["id"] not in ids] if u["betrag_cent"] > 0 else [],
        "kategorie_id": match.kategorie_vorschlag(db, u),
        "belege": match.beleg_treffer(db, u),
        "dauerbelege": match.dauerbeleg_treffer(db, u),
        "buchungen": match.buchung_treffer(db, u),
        "alle_belege": match.alle_offenen_belege(db, u["gewerbe_id"]) if u["betrag_cent"] < 0 else [],
    }


class ZuordnenIn(BaseModel):
    buchung_id: int


@router.post("/umsaetze/{umsatz_id}/zuordnen")
def zuordnen(
    umsatz_id: int, body: ZuordnenIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    """Den Umsatz einer schon vorhandenen Buchung zuordnen (statt eine zweite zu buchen)."""
    u = _umsatz(db, user, umsatz_id)
    if u["buchung_id"] is not None:
        raise HTTPException(409, "Der Umsatz ist schon einer Buchung zugeordnet.")
    b = db.execute("SELECT * FROM buchung WHERE id = ?", (body.buchung_id,)).fetchone()
    if b is None or b["gewerbe_id"] != u["gewerbe_id"]:
        raise HTTPException(404, "Buchung nicht gefunden.")
    if db.execute("SELECT 1 FROM bank_umsatz WHERE buchung_id = ?", (b["id"],)).fetchone():
        raise HTTPException(409, "Diese Buchung gehört schon zu einem anderen Umsatz.")
    db.execute(
        "UPDATE bank_umsatz SET buchung_id = ?, status = 'offen', ignoriert_grund = NULL, "
        "zugeordnet_am = datetime('now') WHERE id = ?",
        (b["id"], umsatz_id),
    )
    db.commit()
    return {"ok": True}


class IgnorierenIn(BaseModel):
    grund: str = Field(min_length=1, max_length=80)


@router.post("/umsaetze/{umsatz_id}/ignorieren")
def ignorieren(
    umsatz_id: int, body: IgnorierenIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)
):
    u = _umsatz(db, user, umsatz_id)
    if u["buchung_id"] is not None:
        raise HTTPException(409, "Der Umsatz ist schon einer Buchung zugeordnet — erst die Verknüpfung lösen.")
    db.execute(
        "UPDATE bank_umsatz SET status = 'ignoriert', ignoriert_grund = ? WHERE id = ?", (body.grund.strip(), umsatz_id)
    )
    db.commit()
    return {"ok": True}


@router.post("/umsaetze/{umsatz_id}/oeffnen")
def wieder_oeffnen(umsatz_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Ignoriert → offen, oder Verknüpfung mit der Buchung lösen (die Buchung bleibt bestehen)."""
    _umsatz(db, user, umsatz_id)
    db.execute(
        "UPDATE bank_umsatz SET status = 'offen', ignoriert_grund = NULL, buchung_id = NULL, zugeordnet_am = NULL, "
        "auto_grund = NULL, auto_buchung = 0, auto_aus = CASE WHEN buchung_id IS NOT NULL THEN 1 ELSE auto_aus END "
        "WHERE id = ?",
        (umsatz_id,),
    )
    db.commit()
    return {"ok": True}


# ── Automatische Zuordnung (services/auto_zuordnung.py) ──────────────────────

class AutomatikIn(BaseModel):
    gewerbe_id: int
    an: bool


@router.put("/automatik")
def automatik_schalten(body: AutomatikIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    db.execute("UPDATE gewerbe SET bank_auto = ? WHERE id = ?", (1 if body.an else 0, body.gewerbe_id))
    db.commit()
    return {"an": body.an}


class AutoLaufIn(BaseModel):
    gewerbe_id: int


@router.post("/automatisch")
def automatisch_zuordnen(body: AutoLaufIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Offene Umsätze jetzt zuordnen, soweit eindeutig (auch mit Fotos im Beleg-Eingang)."""
    g = check_gewerbe(db, user, body.gewerbe_id)
    if not g["bank_auto"]:
        raise HTTPException(409, "Die automatische Zuordnung ist für dieses Gewerbe ausgeschaltet.")
    return auto.lauf(db, body.gewerbe_id, user, bilder=True)


@router.post("/umsaetze/{umsatz_id}/auto-rueckgaengig")
def auto_rueckgaengig(umsatz_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Eine automatische Zuordnung zurücknehmen; danach ordnet Tab diesen Umsatz nie wieder selbst zu."""
    u = _umsatz(db, user, umsatz_id)
    if not u["auto_grund"]:
        raise HTTPException(409, "Dieser Umsatz wurde nicht automatisch zugeordnet.")
    auto.rueckgaengig(db, u)
    return {"ok": True}


# ── Bankabruf (Enable Banking, services/bank_abruf.py) ──────────────────────

def _verbindung(db: sqlite3.Connection, user: dict, verbindung_id: int) -> sqlite3.Row:
    v = db.execute("SELECT * FROM bank_verbindung WHERE id = ?", (verbindung_id,)).fetchone()
    if v is None:
        raise HTTPException(404, "Verbindung nicht gefunden.")
    check_gewerbe(db, user, v["gewerbe_id"])
    return v


def _psu(request: Request) -> dict:
    """Nutzer sitzt davor: IP + Browser an die Bank (zählt nicht gegen die Hintergrund-Abrufe)."""
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (request.client.host if request.client else "")
    return {"Psu-Ip-Address": ip, "Psu-User-Agent": request.headers.get("user-agent", "")[:300]}


@router.get("/abruf")
def abruf_status(gewerbe_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, gewerbe_id)
    verbindungen = []
    for v in db.execute(
        "SELECT * FROM bank_verbindung WHERE gewerbe_id = ? AND status IN ('aktiv','abgelaufen','fehler') ORDER BY id",
        (gewerbe_id,),
    ):
        konten = db.execute("SELECT id, name, iban FROM bankkonto WHERE verbindung_id = ? ORDER BY name", (v["id"],)).fetchall()
        verbindungen.append({
            "id": v["id"], "bank_name": v["bank_name"], "status": v["status"], "gueltig_bis": v["gueltig_bis"],
            "letzter_abruf": v["letzter_abruf"], "letzter_fehler": v["letzter_fehler"],
            "konten": [dict(k) for k in konten],
        })
    return {"konfiguriert": abruf.konfiguriert(), "verbindungen": verbindungen}


@router.get("/abruf/banken")
def abruf_banken(land: str = "DE", user: dict = Depends(get_current_user)):
    if not abruf.konfiguriert():
        raise HTTPException(400, "Bankabruf ist auf diesem Server nicht eingerichtet.")
    try:
        return abruf.banken(land[:2])
    except abruf.AbrufFehler as e:
        raise HTTPException(502, str(e))


class AbrufStartIn(BaseModel):
    gewerbe_id: int
    bank_name: str = Field(min_length=1, max_length=200)
    land: str = Field(default="DE", min_length=2, max_length=2)
    psu_type: str = Field(default="personal", pattern="^(personal|business)$")


@router.post("/abruf/start")
def abruf_start(body: AbrufStartIn, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    check_gewerbe(db, user, body.gewerbe_id)
    if not abruf.konfiguriert():
        raise HTTPException(400, "Bankabruf ist auf diesem Server nicht eingerichtet.")
    try:
        url = abruf.starten(db, gewerbe_id=body.gewerbe_id, bank_name=body.bank_name, land=body.land,
                            psu_type=body.psu_type, email=user["email"])
    except abruf.AbrufFehler as e:
        raise HTTPException(502, str(e))
    return {"url": url}


class AbrufAbschlussIn(BaseModel):
    code: str = Field(min_length=1, max_length=2000)
    state: str = Field(min_length=1, max_length=200)


@router.post("/abruf/abschliessen")
def abruf_abschliessen(
    body: AbrufAbschlussIn, request: Request,
    user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db),
):
    v = abruf.ausstehende(db, body.state)
    if v is None:
        raise HTTPException(400, "Diese Anmeldung bei der Bank ist abgelaufen oder unbekannt — bitte noch einmal verbinden.")
    check_gewerbe(db, user, v["gewerbe_id"])
    try:
        erg = abruf.abschliessen(db, v, body.code, _psu(request))
    except abruf.AbrufFehler as e:
        db.rollback()
        db.execute("UPDATE bank_verbindung SET status = 'fehler', letzter_fehler = ? WHERE id = ? AND status = 'ausstehend'",
                   (str(e)[:500], v["id"]))
        db.commit()
        raise HTTPException(502, str(e))
    try:
        erg["automatisch"] = auto.lauf(db, v["gewerbe_id"], user, bilder=False)
    except Exception:
        db.rollback()
        logging.getLogger("tab.auto_zuordnung").exception("Auto-Zuordnung nach dem Abruf fehlgeschlagen")
    return {"gewerbe_id": v["gewerbe_id"], "bank_name": v["bank_name"], **erg}


@router.post("/abruf/{verbindung_id}/abrufen")
def abruf_jetzt(
    verbindung_id: int, request: Request,
    user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db),
):
    v = _verbindung(db, user, verbindung_id)
    try:
        erg = abruf.abrufen(db, v["id"], email=user["email"], psu=_psu(request))
    except abruf.AbrufFehler as e:
        raise HTTPException(502, str(e))
    try:
        erg["automatisch"] = auto.lauf(db, v["gewerbe_id"], user, bilder=False)
    except Exception:
        db.rollback()
        logging.getLogger("tab.auto_zuordnung").exception("Auto-Zuordnung nach dem Abruf fehlgeschlagen")
    return erg


@router.delete("/abruf/{verbindung_id}")
def abruf_trennen(verbindung_id: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    abruf.trennen(db, _verbindung(db, user, verbindung_id))
    return {"ok": True}
