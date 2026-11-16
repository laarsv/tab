"""Umsatzsteuer-Voranmeldung: Werte für ELSTER je Zeitraum (services/ust_voranmeldung.py). Nur lesen — Tab übermittelt
nichts. „Übermittelt“ ist die Erledigt-Markierung der Fristen-Seite (`frist_erledigt`, Schlüssel ustva:<gewerbe>:<zeitraum>)."""
from __future__ import annotations

import csv
import datetime as dt
import io
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Response

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services import besteuerung as best
from ..services import ust_voranmeldung as ustva

router = APIRouter(prefix="/api/umsatzsteuer", tags=["umsatzsteuer"])


def _erledigt(db: sqlite3.Connection, email: str) -> dict[str, str]:
    return {r["schluessel"]: r["erledigt_am"]
            for r in db.execute("SELECT schluessel, erledigt_am FROM frist_erledigt WHERE email = ?", (email,))}


def _jahr_daten(db: sqlite3.Connection, user: dict, gewerbe_id: int, jahr: int) -> dict:
    g = check_gewerbe(db, user, gewerbe_id)
    art = best.art(db, gewerbe_id, jahr)
    heute = dt.date.today().isoformat()
    out = {
        "gewerbe_id": gewerbe_id, "jahr": jahr, "besteuerung": art,
        "zeitraum": g["ustva_zeitraum"], "zeitraum_label": ustva.ZEITRAUM_LABEL[g["ustva_zeitraum"]],
        "dauerfrist": bool(g["ustva_dauerfrist"]), "heute": heute, "perioden": [],
    }
    if art != best.REGEL:
        return out
    erledigt = _erledigt(db, user["email"])
    for z in ustva.zeitraeume(jahr, g["ustva_zeitraum"]):
        d = ustva.berechne(db, gewerbe_id, z["von"], z["bis"])
        frist = ustva.abgabefrist(z["bis"], bool(g["ustva_dauerfrist"]))
        schluessel = ustva.frist_schluessel(gewerbe_id, z["key"])
        if erledigt.get(schluessel):
            status = "uebermittelt"
        elif z["von"] > heute:
            status = "kommt"
        elif z["bis"] >= heute:
            status = "laeuft"
        elif frist < heute:
            status = "ueberfaellig"
        else:
            status = "offen"
        out["perioden"].append({**z, **d, "frist": frist, "schluessel": schluessel,
                                "uebermittelt_am": erledigt.get(schluessel), "status": status})
    j = ustva.berechne(db, gewerbe_id, f"{jahr}-01-01", f"{jahr}-12-31")
    jschl = ustva.jahreserklaerung_schluessel(gewerbe_id, jahr)
    out["jahr_summe"] = {**j, "frist": ustva.jahreserklaerung_frist(jahr), "schluessel": jschl,
                         "uebermittelt_am": erledigt.get(jschl),
                         "summe_voranmeldungen_cent": sum(p["kz83_cent"] for p in out["perioden"])}
    return out


@router.get("")
def jahresuebersicht(gewerbe_id: int, jahr: int, user: dict = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    return _jahr_daten(db, user, gewerbe_id, jahr)


@router.get("/zeitraum")
def zeitraum(gewerbe_id: int, von: str, bis: str, user: dict = Depends(get_current_user),
             db: sqlite3.Connection = Depends(get_db)):
    """Kennzahlen mit den Positionen dahinter (zum Nachprüfen)."""
    check_gewerbe(db, user, gewerbe_id)
    try:
        v, b = dt.date.fromisoformat(von), dt.date.fromisoformat(bis)
    except ValueError:
        raise HTTPException(400, "Datum im Format JJJJ-MM-TT angeben.")
    if v > b or v.year != b.year:
        raise HTTPException(400, "Der Zeitraum muss innerhalb eines Jahres liegen.")
    if not best.ist_regel(db, gewerbe_id, v.year):
        raise HTTPException(400, f"{v.year} ist ein Kleinunternehmer-Jahr — dafür gibt es keine Voranmeldung.")
    return ustva.berechne(db, gewerbe_id, von, bis, mit_positionen=True)


def _de(cent: int) -> str:
    return f"{cent / 100:.2f}".replace(".", ",")


@router.get("/voranmeldungen.csv")
def csv_export(gewerbe_id: int, jahr: int, user: dict = Depends(get_current_user),
               db: sqlite3.Connection = Depends(get_db)):
    d = _jahr_daten(db, user, gewerbe_id, jahr)
    if d["besteuerung"] != best.REGEL:
        raise HTTPException(400, f"{jahr} ist ein Kleinunternehmer-Jahr — dafür gibt es keine Voranmeldung.")
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Zeitraum", "Von", "Bis", "Kz 81 (EUR)", "Steuer 19 % (EUR)", "Kz 86 (EUR)", "Steuer 7 % (EUR)",
                "Kz 35 (EUR)", "Kz 36 (EUR)", "Kz 48 (EUR)", "Kz 66 (EUR)", "Kz 83 (EUR)", "Abgabefrist", "Übermittelt am"])
    zeilen = d["perioden"] + [{**d["jahr_summe"], "label": f"Jahr {jahr}", "frist": d["jahr_summe"]["frist"]}]
    for p in zeilen:
        kz = {k["kz"]: k for k in p["kennzahlen"]}
        w.writerow([
            p["label"], p["von"], p["bis"],
            kz.get("81", {}).get("bemessung_eur", 0), _de(kz.get("81", {}).get("steuer_cent", 0)),
            kz.get("86", {}).get("bemessung_eur", 0), _de(kz.get("86", {}).get("steuer_cent", 0)),
            kz.get("35", {}).get("bemessung_eur", 0), _de(kz.get("35", {}).get("steuer_cent", 0)),
            kz.get("48", {}).get("bemessung_eur", 0), _de(kz.get("66", {}).get("steuer_cent", 0)),
            _de(p["kz83_cent"]), p["frist"], p.get("uebermittelt_am") or "",
        ])
    return Response(
        ("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="umsatzsteuer-{jahr}.csv"'},
    )
