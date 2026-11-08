"""Übersicht (Startseite): Kennzahlen, was gerade wartet, offene Rechnungen, zuletzt Gebuchtes.

Aufbau nach Haben (Aufgabenliste + Kennzahlen), eigenständig umgesetzt. Alles nur lesend und aus
vorhandenen Diensten — die Übersicht rechnet nichts Eigenes, sie sammelt ein.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

from fastapi import APIRouter, Depends

from ..auth.deps import check_gewerbe, get_current_user
from ..db import get_db
from ..services import abschluss as abschluss_svc
from ..services import dauerbelege as dauer_svc
from ..services import kennzahlen as kz
from ..services.mahnwesen import effektive_faelligkeit, tage_ueberfaellig
from ..services.steuerfristen import DRINGEND_TAGE
from ..services.zahlungen import offen_cent
from .fristen import fristen_des_nutzers

router = APIRouter(prefix="/api/uebersicht", tags=["uebersicht"], dependencies=[Depends(get_current_user)])

MAX_RECHNUNGEN = 5
MAX_BUCHUNGEN = 5
TON_RANG = {"neg": 0, "warn": 1, "leise": 2}


def _euro(cent: int) -> str:
    s = f"{abs(cent) / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'−' if cent < 0 else ''}{s} €"


def _de(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


def _plural(n: int, eins: str, viele: str) -> str:
    return f"{n} {eins if n == 1 else viele}"


def _forderungen(db: sqlite3.Connection, gewerbe_id: int, heute: str) -> dict:
    """Versendete Rechnungen mit offenem Rest (nach Teilzahlungen und Skonto)."""
    items = []
    for r in db.execute("SELECT * FROM rechnung WHERE gewerbe_id = ? AND status = 'versendet'", (gewerbe_id,)):
        offen = offen_cent(db, r)
        if offen <= 0:
            continue
        faellig = effektive_faelligkeit(r["datum"], r["faellig_am"])
        items.append(
            {
                "id": r["id"],
                "nummer": r["nummer"],
                "empfaenger_name": r["empfaenger_name"],
                "faellig_am": faellig,
                "tage_ueberfaellig": tage_ueberfaellig(faellig, heute),
                "ueberfaellig": faellig < heute,
                "offen_cent": offen,
            }
        )
    # Überfällige zuerst (am längsten), dann nach Fälligkeit
    items.sort(key=lambda i: (not i["ueberfaellig"], i["faellig_am"], i["nummer"]))
    ueberf = [i for i in items if i["ueberfaellig"]]
    return {
        "anzahl": len(items),
        "offen_cent": sum(i["offen_cent"] for i in items),
        "ueberfaellig_anzahl": len(ueberf),
        "ueberfaellig_cent": sum(i["offen_cent"] for i in ueberf),
        "aelteste_tage": max((i["tage_ueberfaellig"] for i in ueberf), default=0),
        "items": items[:MAX_RECHNUNGEN],
    }


def _letzte_buchungen(db: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    out = []
    heads = db.execute(
        "SELECT id, datum, beschreibung FROM buchung WHERE gewerbe_id = ? ORDER BY datum DESC, id DESC LIMIT ?",
        (gewerbe_id, MAX_BUCHUNGEN),
    ).fetchall()
    for h in heads:
        pos = db.execute(
            "SELECT p.betrag_cent, k.name, k.typ FROM buchung_position p "
            "JOIN kategorie k ON k.id = p.kategorie_id WHERE p.buchung_id = ? ORDER BY p.id",
            (h["id"],),
        ).fetchall()
        typen = {p["typ"] for p in pos}
        out.append(
            {
                "id": h["id"],
                "datum": h["datum"],
                "beschreibung": h["beschreibung"],
                "kategorie": pos[0]["name"] if len(pos) == 1 else f"{len(pos)} Positionen",
                "typ": next(iter(typen)) if len(typen) == 1 else None,  # gemischt → ohne Vorzeichen
                "summe_cent": sum(p["betrag_cent"] for p in pos),
            }
        )
    return out


def _aufgaben(db: sqlite3.Connection, user: dict, gewerbe_id: int, heute: str, forderungen: dict) -> list[dict]:
    """Was gerade wartet — jede Zeile mit Ziel und der einen Hauptaktion. Nur, was wirklich offen ist."""
    aufgaben: list[dict] = []

    def add(schluessel: str, ton: str, titel: str, sub: str, to: str, aktion: str) -> None:
        aufgaben.append(
            {"schluessel": schluessel, "ton": ton, "titel": titel, "sub": sub, "to": to, "aktion": aktion}
        )

    # Überfällige Rechnungen
    n = forderungen["ueberfaellig_anzahl"]
    if n:
        add(
            "ueberfaellig",
            "neg",
            _plural(n, "Rechnung überfällig", "Rechnungen überfällig"),
            f"{_euro(forderungen['ueberfaellig_cent'])} offen · die älteste seit {forderungen['aelteste_tage']} Tagen",
            "/rechnungen/mahnwesen",
            "Mahnen",
        )

    # Steuerfristen (nur, was dringend ist — dieselbe Regel wie der Zähler in der Seitenleiste)
    dringend = [
        f
        for f in fristen_des_nutzers(db, user["email"])
        if f["erledigbar"] and not f["erledigt_am"] and f["tage_bis"] <= DRINGEND_TAGE
    ]
    if dringend:
        f = dringend[0]
        tage = f["tage_bis"]
        wann = (
            f"seit {-tage} Tagen überfällig" if tage < 0 else "heute fällig" if tage == 0 else f"fällig in {tage} Tagen"
        )
        rest = f" · und {len(dringend) - 1} weitere" if len(dringend) > 1 else ""
        add("frist", "neg" if tage < 0 else "warn", f["titel"], f"{wann} · {_de(f['faellig_am'])}{rest}", "/fristen", "Ansehen")

    # Dauerbelege mit fälligen Terminen
    namen, termine = [], 0
    for r in db.execute("SELECT * FROM dauerbeleg WHERE gewerbe_id = ? AND aktiv = 1 ORDER BY bezeichnung", (gewerbe_id,)):
        t = len(dauer_svc.faellige_termine(r, heute))
        if t:
            termine += t
            namen.append(r["bezeichnung"])
    if termine:
        zeigen = ", ".join(namen[:3]) + (" …" if len(namen) > 3 else "")
        add(
            "dauerbelege",
            "warn",
            _plural(termine, "Dauerbeleg-Termin fällig", "Dauerbeleg-Termine fällig"),
            zeigen,
            "/dauerbelege",
            "Buchen",
        )

    # Beleg-Eingang
    row = db.execute(
        "SELECT COUNT(*) AS n, COALESCE(SUM(faellig_am IS NOT NULL AND faellig_am < ?), 0) AS ueberf "
        "FROM beleg WHERE gewerbe_id = ? AND buchung_id IS NULL",
        (heute, gewerbe_id),
    ).fetchone()
    if row["n"]:
        ueberf = row["ueberf"]
        add(
            "eingang",
            "neg" if ueberf else "warn",
            _plural(row["n"], "Beleg im Eingang", "Belege im Eingang"),
            f"{ueberf} davon überfällig zu zahlen" if ueberf else "Noch nicht verbucht",
            "/buchungen",
            "Abarbeiten",
        )

    # Bankumsätze ohne Zuordnung
    konten = db.execute(
        """
        SELECT k.name,
          (SELECT COUNT(*) FROM bank_umsatz u WHERE u.konto_id = k.id AND u.buchung_id IS NULL AND u.status = 'offen') AS offen,
          (SELECT MAX(bis) FROM bank_import i WHERE i.konto_id = k.id) AS bis
        FROM bankkonto k WHERE k.gewerbe_id = ? ORDER BY k.name COLLATE NOCASE
        """,
        (gewerbe_id,),
    ).fetchall()
    offen = sum(k["offen"] for k in konten)
    if offen:
        mit = [k for k in konten if k["offen"]]
        if len(mit) == 1:
            sub = mit[0]["name"] + (f" · Auszug bis {_de(mit[0]['bis'])}" if mit[0]["bis"] else "")
        else:
            sub = f"auf {len(mit)} Konten"
        add("bank", "warn", _plural(offen, "Bankumsatz ohne Zuordnung", "Bankumsätze ohne Zuordnung"), sub, "/bank", "Zuordnen")

    # Rechnungsentwürfe
    n = db.execute("SELECT COUNT(*) FROM rechnung WHERE gewerbe_id = ? AND status = 'entwurf'", (gewerbe_id,)).fetchone()[0]
    if n:
        add("entwuerfe", "leise", _plural(n, "Rechnungsentwurf", "Rechnungsentwürfe"), "Noch nicht versendet", "/rechnungen", "Öffnen")

    # Angebote ohne Antwort
    ang = db.execute(
        "SELECT gueltig_bis FROM angebot WHERE gewerbe_id = ? AND status = 'versendet' ORDER BY gueltig_bis",
        (gewerbe_id,),
    ).fetchall()
    if ang:
        abgelaufen = sum(1 for a in ang if a["gueltig_bis"] < heute)
        add(
            "angebote",
            "warn" if abgelaufen else "leise",
            _plural(len(ang), "Angebot wartet auf Antwort", "Angebote warten auf Antwort"),
            f"{abgelaufen} davon abgelaufen" if abgelaufen else f"die erste gilt bis {_de(ang[0]['gueltig_bis'])}",
            "/rechnungen/angebote",
            "Öffnen",
        )

    # Vergangenes Jahr mit Buchungen, das noch nicht abgeschlossen ist (das jüngste genügt)
    for j in abschluss_svc.jahre(db, gewerbe_id):
        if j["kann_schliessen"] and not j["abgeschlossen"] and j["anzahl_buchungen"] > 0:
            add(
                "abschluss",
                "leise",
                f"Jahr {j['jahr']} abschließen",
                f"{_plural(j['anzahl_buchungen'], 'Buchung', 'Buchungen')} · danach lässt sich nichts mehr versehentlich ändern",
                "/abschluss",
                "Ansehen",
            )
            break

    aufgaben.sort(key=lambda a: TON_RANG[a["ton"]])  # stabil: innerhalb eines Tons bleibt die Reihenfolge
    return aufgaben


@router.get("")
def uebersicht(
    gewerbe_id: int,
    jahr: int,
    user: dict = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    check_gewerbe(db, user, gewerbe_id)
    heute = dt.date.today().isoformat()
    forderungen = _forderungen(db, gewerbe_id, heute)
    aktuell = kz.summen(db, gewerbe_id, jahr)
    vorjahr = kz.summen(db, gewerbe_id, jahr - 1)
    return {
        "heute": heute,
        "gewerbe_id": gewerbe_id,
        "jahr": jahr,
        "kennzahlen": {**kz.mit_ku_guard(aktuell), "vorjahr": vorjahr},
        "forderungen": forderungen,
        "aufgaben": _aufgaben(db, user, gewerbe_id, heute, forderungen),
        "letzte_buchungen": _letzte_buchungen(db, gewerbe_id),
    }
