"""KI-Änderungsvorschläge: Ein Assistent ändert nichts selbst, er schlägt vor — der Inhaber entscheidet in Tab.

Ablauf: Ein MCP-Werkzeug (nur mit der Stufe „Vorschläge machen“) prüft die Eingaben genau wie die normale Oberfläche
(dieselben Pydantic-Modelle, dieselbe Mandantenprüfung) und legt in ki_vorschlag einen Eintrag ab — über eine EIGENE,
schmale Verbindung, die nur dort schreibt. Die Hauptverbindung des Assistenten bleibt auf query_only. Der Inhaber sieht
Vorher/Nachher auf der Übersicht und übernimmt oder verwirft. „Übernehmen“ führt die vorhandenen Routen aus (also mit
allen Prüfungen), im Änderungsprotokoll steht der Vorschlag als Akteur. Hat sich das Ziel seit dem Vorschlag geändert,
wird nicht mehr übernommen.

Bewusst nur drei Arten, alle ohne Geldbewegung und ohne Versand: Abo ändern (Intervall, nächster Termin, pausieren,
Positionen), Rechnungsentwurf anlegen, Rechnungsentwurf ändern. Buchen, Löschen, Versenden, Mahnen, Status, Jahresabschluss
gibt es hier nicht.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from ..auth.deps import check_gewerbe, nur_inhaber
from ..db import _connect, get_db
from . import abos, rechnungen

router = APIRouter(prefix="/api/ki/vorschlaege", tags=["ki"])

MAX_OFFEN = 20
MAX_POSITIONEN = 30
MAX_BEGRUENDUNG = 500
INTERVALL_TEXT = {"monatlich": "monatlich", "vierteljaehrlich": "vierteljährlich", "jaehrlich": "jährlich"}


class VorschlagFehler(Exception):
    """Eingabe des Assistenten ist nicht zulässig — Text geht als Werkzeugfehler zurück."""


# ── Hilfen ──────────────────────────────────────────────────────────────────

def _euro(cent: int) -> str:
    s = f"{abs(cent) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'−' if cent < 0 else ''}{s} €"


def _de(iso: str | None) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else "—"


def _hash(daten) -> str:
    return hashlib.sha256(json.dumps(daten, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def _menge(m) -> str:
    return str(int(m)) if float(m) == int(m) else str(m).replace(".", ",")


def _pos_text(positionen: list[dict]) -> str:
    zeilen = [f"{_menge(p['menge'])} × {p['beschreibung']} à {_euro(p['einzelpreis_cent'])}" for p in positionen]
    summe = sum(round(p["menge"] * p["einzelpreis_cent"]) for p in positionen)
    return "\n".join(zeilen) + f"\nSumme {_euro(summe)}"


def _fehler_text(e: ValidationError) -> str:
    f = e.errors()[0]
    wo = ".".join(str(x) for x in f["loc"])
    return f"Ungültige Eingabe ({wo}): {f['msg']}"


def _begruendung(a: dict) -> str | None:
    b = a.get("begruendung")
    if b is None:
        return None
    if not isinstance(b, str):
        raise VorschlagFehler("„begruendung“ muss Text sein.")
    return b.strip()[:MAX_BEGRUENDUNG] or None


def _positionen(a: dict, name: str = "positionen") -> list[dict]:
    p = a.get(name)
    if not isinstance(p, list) or not p or len(p) > MAX_POSITIONEN or not all(isinstance(x, dict) for x in p):
        raise VorschlagFehler(f"„{name}“: 1 bis {MAX_POSITIONEN} Positionen mit beschreibung, menge, einzelpreis_cent.")
    return [{k: x.get(k) for k in ("beschreibung", "menge", "einzelpreis_cent")} for x in p]


def _id(a: dict, name: str) -> int:
    v = a.get(name)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or int(v) != v:
        raise VorschlagFehler(f"Parameter „{name}“ fehlt oder ist keine ganze Zahl.")
    return int(v)


# ── Abo ändern ──────────────────────────────────────────────────────────────

def _abo_basis(row: sqlite3.Row) -> dict:
    return {"intervall": row["intervall"], "naechste_am": row["naechste_am"], "aktiv": bool(row["aktiv"]), "positionen": _hash(row["positionen_json"])}


def vorschlag_abo(db: sqlite3.Connection, user: dict, a: dict) -> dict:
    abo_id = _id(a, "abo_id")
    row = db.execute("SELECT * FROM rechnung_abo WHERE id = ?", (abo_id,)).fetchone()
    if row is None:
        raise VorschlagFehler("Abo nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    felder = {k: a[k] for k in ("intervall", "naechste_am", "aktiv", "positionen") if a.get(k) is not None}
    if not felder:
        raise VorschlagFehler("Keine Änderung angegeben (intervall, naechste_am, aktiv oder positionen).")
    if "positionen" in felder:
        felder["positionen"] = _positionen(felder)
    if "aktiv" in felder and not isinstance(felder["aktiv"], bool):
        raise VorschlagFehler("„aktiv“ muss true oder false sein.")
    try:
        patch = abos.AboPatch(**felder)
    except ValidationError as e:
        raise VorschlagFehler(_fehler_text(e))
    jetzt = json.loads(row["positionen_json"])
    anzeige = []
    if patch.intervall is not None and patch.intervall != row["intervall"]:
        anzeige.append({"feld": "Rhythmus", "vorher": INTERVALL_TEXT[row["intervall"]], "nachher": INTERVALL_TEXT[patch.intervall]})
    if patch.naechste_am is not None and patch.naechste_am != row["naechste_am"]:
        anzeige.append({"feld": "Nächster Termin", "vorher": _de(row["naechste_am"]), "nachher": _de(patch.naechste_am)})
    if patch.aktiv is not None and patch.aktiv != bool(row["aktiv"]):
        anzeige.append({"feld": "Status", "vorher": "aktiv" if row["aktiv"] else "pausiert", "nachher": "aktiv" if patch.aktiv else "pausiert"})
    if patch.positionen is not None:
        neu = [p.model_dump() for p in patch.positionen]
        if neu != [{k: p.get(k) for k in ("beschreibung", "menge", "einzelpreis_cent")} for p in jetzt]:
            anzeige.append({"feld": "Positionen", "vorher": _pos_text(jetzt), "nachher": _pos_text(neu)})
    if not anzeige:
        raise VorschlagFehler("Das entspricht schon dem aktuellen Stand — nichts zu ändern.")
    payload = {k: v for k, v in felder.items()}
    return dict(gewerbe_id=row["gewerbe_id"], art="abo_aendern", ziel_id=abo_id, titel=f"Abo „{row['empfaenger_name']}“ ändern",
                begruendung=_begruendung(a), payload=payload, anzeige=anzeige, basis=_abo_basis(row))


# ── Rechnungsentwurf anlegen ────────────────────────────────────────────────

def vorschlag_entwurf_neu(db: sqlite3.Connection, user: dict, a: dict) -> dict:
    gid = _id(a, "gewerbe_id")
    check_gewerbe(db, user, gid)
    daten = {
        "gewerbe_id": gid,
        "datum": a.get("datum") or dt.date.today().isoformat(),
        "empfaenger_name": a.get("empfaenger_name"),
        "positionen": _positionen(a),
    }
    for k in ("leistungsdatum", "zahlungsziel_tage", "notiz", "bestellnummer", "empfaenger_anschrift", "empfaenger_email"):
        if a.get(k) is not None:
            daten[k] = a[k]
    try:
        body = rechnungen.RechnungIn(**daten)
    except ValidationError as e:
        raise VorschlagFehler(_fehler_text(e))
    abstand = (dt.date.fromisoformat(body.datum) - dt.date.today()).days
    if not -400 <= abstand <= 60:
        raise VorschlagFehler("Das Rechnungsdatum liegt zu weit von heute entfernt (höchstens 400 Tage zurück, 60 voraus).")
    anzeige = [
        {"feld": "Empfänger", "vorher": "—", "nachher": body.empfaenger_name},
        {"feld": "Rechnungsdatum", "vorher": "—", "nachher": _de(body.datum)},
        {"feld": "Positionen", "vorher": "—", "nachher": _pos_text([p.model_dump() for p in body.positionen])},
    ]
    if body.zahlungsziel_tage is not None:
        anzeige.append({"feld": "Zahlungsziel", "vorher": "—", "nachher": f"{body.zahlungsziel_tage} Tage"})
    if body.bestellnummer:
        anzeige.append({"feld": "Ihre Bestellnummer", "vorher": "—", "nachher": body.bestellnummer})
    if body.notiz:
        anzeige.append({"feld": "Notiz", "vorher": "—", "nachher": body.notiz})
    return dict(gewerbe_id=gid, art="entwurf_neu", ziel_id=None, titel=f"Rechnungsentwurf für „{body.empfaenger_name}“ anlegen",
                begruendung=_begruendung(a), payload=body.model_dump(), anzeige=anzeige, basis=None)


# ── Rechnungsentwurf ändern ─────────────────────────────────────────────────

def _entwurf_basis(db: sqlite3.Connection, row: sqlite3.Row) -> dict:
    pos = [dict(p) for p in db.execute("SELECT beschreibung, menge, einzelpreis_cent FROM rechnung_position WHERE rechnung_id = ? ORDER BY id", (row["id"],))]
    return {"status": row["status"], "zahlungsziel_tage": row["zahlungsziel_tage"], "notiz": row["notiz"], "bestellnummer": row["bestellnummer"],
            "leistungsdatum": row["leistungsdatum"], "positionen": _hash(pos)}


def vorschlag_entwurf_aendern(db: sqlite3.Connection, user: dict, a: dict) -> dict:
    rid = _id(a, "rechnung_id")
    row = db.execute("SELECT * FROM rechnung WHERE id = ?", (rid,)).fetchone()
    if row is None:
        raise VorschlagFehler("Rechnung nicht gefunden.")
    check_gewerbe(db, user, row["gewerbe_id"])
    if row["status"] != "entwurf":
        raise VorschlagFehler("Nur Entwürfe lassen sich ändern. Eine versendete Rechnung bleibt unverändert (bei Fehlern stornieren).")
    felder = {k: a[k] for k in ("zahlungsziel_tage", "notiz", "bestellnummer", "leistungsdatum", "positionen") if a.get(k) is not None}
    if not felder:
        raise VorschlagFehler("Keine Änderung angegeben (zahlungsziel_tage, notiz, bestellnummer, leistungsdatum oder positionen).")
    if "positionen" in felder:
        felder["positionen"] = _positionen(felder)
    try:
        patch = rechnungen.RechnungPatch(**felder)
    except ValidationError as e:
        raise VorschlagFehler(_fehler_text(e))
    basis = _entwurf_basis(db, row)
    pos_jetzt = [dict(p) for p in db.execute("SELECT beschreibung, menge, einzelpreis_cent FROM rechnung_position WHERE rechnung_id = ? ORDER BY id", (rid,))]
    anzeige = []
    for feld, schluessel, label in (("zahlungsziel_tage", "zahlungsziel_tage", "Zahlungsziel (Tage)"), ("notiz", "notiz", "Notiz"),
                                     ("bestellnummer", "bestellnummer", "Ihre Bestellnummer"), ("leistungsdatum", "leistungsdatum", "Leistungsdatum")):
        neu = getattr(patch, feld)
        if neu is not None and (str(neu).strip() or None) != (str(row[schluessel]) if row[schluessel] is not None else None):
            anzeige.append({"feld": label, "vorher": str(row[schluessel]) if row[schluessel] is not None else "—", "nachher": str(neu)})
    if patch.positionen is not None:
        neu = [p.model_dump() for p in patch.positionen]
        if neu != [{k: p.get(k) for k in ("beschreibung", "menge", "einzelpreis_cent")} for p in pos_jetzt]:
            anzeige.append({"feld": "Positionen", "vorher": _pos_text(pos_jetzt), "nachher": _pos_text(neu)})
    if not anzeige:
        raise VorschlagFehler("Das entspricht schon dem aktuellen Stand — nichts zu ändern.")
    return dict(gewerbe_id=row["gewerbe_id"], art="entwurf_aendern", ziel_id=rid, titel=f"Entwurf {row['nummer']} ändern",
                begruendung=_begruendung(a), payload=felder, anzeige=anzeige, basis=basis)


# ── Ablegen (einzige Schreibstelle des Assistenten) ─────────────────────────

def anlegen(owner_email: str, quelle: str, v: dict) -> int:
    """Eigene Verbindung, schreibt nur in ki_vorschlag. Die Hauptverbindung des Assistenten bleibt query_only."""
    con = _connect(actor=quelle)
    try:
        offen = con.execute("SELECT COUNT(*) FROM ki_vorschlag WHERE owner_email = ? AND status = 'offen'", (owner_email,)).fetchone()[0]
        if offen >= MAX_OFFEN:
            raise VorschlagFehler(f"Es warten schon {MAX_OFFEN} Vorschläge auf eine Entscheidung. Bitte erst diese abarbeiten lassen.")
        cur = con.execute(
            "INSERT INTO ki_vorschlag (owner_email, gewerbe_id, art, ziel_id, titel, begruendung, payload, anzeige, basis, quelle) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (owner_email, v["gewerbe_id"], v["art"], v["ziel_id"], v["titel"], v["begruendung"], json.dumps(v["payload"], ensure_ascii=False),
             json.dumps(v["anzeige"], ensure_ascii=False), json.dumps(v["basis"]) if v["basis"] is not None else None, quelle),
        )
        con.commit()
        return cur.lastrowid
    finally:
        con.close()


# ── Inhaber: ansehen, übernehmen, verwerfen ─────────────────────────────────

def _ausgabe(r: sqlite3.Row) -> dict:
    return {
        "id": r["id"], "art": r["art"], "titel": r["titel"], "begruendung": r["begruendung"], "anzeige": json.loads(r["anzeige"]),
        "quelle": r["quelle"], "status": r["status"], "fehler": r["fehler"], "ergebnis_id": r["ergebnis_id"],
        "gewerbe_id": r["gewerbe_id"], "created_at": r["created_at"], "entschieden_am": r["entschieden_am"],
    }


@router.get("")
def liste(alle: bool = False, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    sql = "SELECT * FROM ki_vorschlag WHERE owner_email = ?" + ("" if alle else " AND status = 'offen'") + " ORDER BY id DESC LIMIT 50"
    return [_ausgabe(r) for r in db.execute(sql, (user["email"],))]


def _eigener(db: sqlite3.Connection, user: dict, vid: int) -> sqlite3.Row:
    r = db.execute("SELECT * FROM ki_vorschlag WHERE id = ? AND owner_email = ?", (vid, user["email"])).fetchone()
    if r is None:
        raise HTTPException(404, "Vorschlag nicht gefunden.")
    return r


@router.post("/{vid}/verwerfen")
def verwerfen(vid: int, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    r = _eigener(db, user, vid)
    if r["status"] != "offen":
        raise HTTPException(409, "Dieser Vorschlag ist schon entschieden.")
    db.execute("UPDATE ki_vorschlag SET status = 'verworfen', entschieden_am = datetime('now') WHERE id = ?", (vid,))
    db.commit()
    return _ausgabe(db.execute("SELECT * FROM ki_vorschlag WHERE id = ?", (vid,)).fetchone())


@router.post("/{vid}/uebernehmen")
def uebernehmen(vid: int, user: dict = Depends(nur_inhaber), db: sqlite3.Connection = Depends(get_db)):
    r = _eigener(db, user, vid)
    if r["status"] != "offen":
        raise HTTPException(409, "Dieser Vorschlag ist schon entschieden.")
    payload = json.loads(r["payload"])
    db.actor = f"{user['email']} (KI-Vorschlag {vid}, {r['quelle']})"  # steht so im Änderungsprotokoll
    ergebnis_id = None
    try:
        if r["art"] == "abo_aendern":
            row = db.execute("SELECT * FROM rechnung_abo WHERE id = ?", (r["ziel_id"],)).fetchone()
            if row is None:
                raise HTTPException(404, "Das Abo gibt es nicht mehr.")
            if _abo_basis(row) != json.loads(r["basis"]):
                raise HTTPException(409, "Das Abo hat sich seit dem Vorschlag geändert. Bitte verwerfen und neu vorschlagen lassen.")
            abos.update_abo(r["ziel_id"], abos.AboPatch(**payload), user, db)
            ergebnis_id = r["ziel_id"]
        elif r["art"] == "entwurf_neu":
            ergebnis_id = rechnungen.create_rechnung(rechnungen.RechnungIn(**payload), user, db)["id"]
        elif r["art"] == "entwurf_aendern":
            row = db.execute("SELECT * FROM rechnung WHERE id = ?", (r["ziel_id"],)).fetchone()
            if row is None:
                raise HTTPException(404, "Die Rechnung gibt es nicht mehr.")
            if _entwurf_basis(db, row) != json.loads(r["basis"]):
                raise HTTPException(409, "Der Entwurf hat sich seit dem Vorschlag geändert. Bitte verwerfen und neu vorschlagen lassen.")
            rechnungen.update_rechnung(r["ziel_id"], rechnungen.RechnungPatch(**payload), user, db)
            ergebnis_id = r["ziel_id"]
    except HTTPException as e:
        db.rollback()
        if e.status_code != 409:  # Veraltet bleibt offen (verwerfen), alles andere ist gescheitert
            db.execute("UPDATE ki_vorschlag SET status = 'fehlgeschlagen', fehler = ?, entschieden_am = datetime('now') WHERE id = ?", (str(e.detail)[:300], vid))
            db.commit()
        raise
    db.execute("UPDATE ki_vorschlag SET status = 'uebernommen', ergebnis_id = ?, entschieden_am = datetime('now') WHERE id = ?", (ergebnis_id, vid))
    db.commit()
    return _ausgabe(db.execute("SELECT * FROM ki_vorschlag WHERE id = ?", (vid,)).fetchone())
