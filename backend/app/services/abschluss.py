"""Jahresabschluss: Jahr abschließen (sperren + versiegeln), prüfen, wieder öffnen.

Abschließen sperrt Buchungen, Belege, Fahrten und AfA des Jahres (Trigger in services/audit.py)
und legt ein **Siegel** ab: SHA-256 über die Daten des Jahres. „Prüfen“ rechnet das Siegel neu
und vergleicht — so fällt auf, wenn die Datenbank an den Triggern vorbei geändert wurde (direkt per
SQL, durch ein zurückgespieltes Backup). Zusätzlich wird die Hash-Kette des Protokolls geprüft.

Siegel = SHA-256 über vier Abschnitte (je einzeln gehasht, damit eine Abweichung benennt, WO sie
liegt): Buchungen samt Positionen, Belege (mit SHA-256 der Datei), AfA des Jahres (berechnete
Beträge, nicht die Stammdaten) und Fahrten. Wieder öffnen geht nur mit Begründung und steht im
Änderungsprotokoll.

Das ist Nachvollziehbarkeit, keine Steuerberatung und keine GoBD-Zertifizierung.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sqlite3

from ..config import settings
from .afa import jahres_afa_cent
from .audit import jetzt_iso, kette_pruefen, trigger_fehlen

SIEGEL_VERSION = 1
ABSCHNITTE = ("buchungen", "belege", "afa", "fahrten")
ABSCHNITT_NAME = {"buchungen": "Buchungen", "belege": "Belege", "afa": "AfA", "fahrten": "Fahrten"}


class AbschlussError(Exception):
    """Fachlicher Fehler (→ HTTP 400)."""


def _h(daten) -> str:
    text = json.dumps(daten, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _datei_sha256(stored_name: str) -> str:
    pfad = os.path.join(settings.UPLOAD_ROOT, stored_name)
    if not os.path.isfile(pfad):
        return "FEHLT"
    h = hashlib.sha256()
    with open(pfad, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _afa_betrifft(a: sqlite3.Row, jahr: int) -> bool:
    if int(a["anschaffungsdatum"][:4]) > jahr:
        return False
    return not a["abgang_datum"] or int(a["abgang_datum"][:4]) >= jahr


def siegel(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> tuple[str, dict]:
    """(Gesamt-Siegel, Info je Abschnitt: Anzahl + Hash)."""
    j = str(jahr)
    buchungen = []
    for b in conn.execute(
        "SELECT * FROM buchung WHERE gewerbe_id = ? AND substr(datum, 1, 4) = ? ORDER BY id", (gewerbe_id, j)
    ):
        # privat_bp nur, wenn gesetzt: Siegel aus der Zeit vor v24 bleiben nachrechenbar
        pos = [
            [p["id"], p["kategorie_id"], p["betrag_cent"], p["beleg_details"] or ""] + ([p["privat_bp"]] if p["privat_bp"] else [])
            for p in conn.execute("SELECT * FROM buchung_position WHERE buchung_id = ? ORDER BY id", (b["id"],))
        ]
        buchungen.append([b["id"], b["datum"], b["beschreibung"] or "", pos])
    belege = [
        [r["id"], r["buchung_id"], r["original_name"], r["size_bytes"], _datei_sha256(r["stored_name"])]
        for r in conn.execute(
            "SELECT bel.* FROM beleg bel JOIN buchung b ON b.id = bel.buchung_id "
            "WHERE bel.gewerbe_id = ? AND substr(b.datum, 1, 4) = ? ORDER BY bel.id",
            (gewerbe_id, j),
        )
    ]
    # Nur, was die Sperre schützt: Bezeichnung/Beschreibung und ein Abgang NACH dem Jahr bleiben
    # änderbar und gehören deshalb nicht ins Siegel. Ein Abgang im Jahr selbst steckt im berechneten
    # Jahres-AfA-Betrag.
    afa = [
        [
            a["id"], a["kategorie_id"], a["anschaffungsdatum"], a["anschaffungskosten_cent"],
            a["nutzungsdauer_jahre"], a["afa_methode"],
            jahres_afa_cent(
                a["anschaffungskosten_cent"], a["anschaffungsdatum"], a["nutzungsdauer_jahre"], jahr, a["abgang_datum"]
            ),
        ]
        for a in conn.execute("SELECT * FROM afa_buchung WHERE gewerbe_id = ? ORDER BY id", (gewerbe_id,))
        if _afa_betrifft(a, jahr)
    ]
    fahrten = [
        [f["id"], f["datum"], f["ziel"], f["anlass"] or "", f["km"]]
        for f in conn.execute(
            "SELECT * FROM fahrt WHERE gewerbe_id = ? AND substr(datum, 1, 4) = ? ORDER BY id", (gewerbe_id, j)
        )
    ]
    teile = {"buchungen": buchungen, "belege": belege, "afa": afa, "fahrten": fahrten}
    info = {name: {"anzahl": len(daten), "hash": _h(daten)} for name, daten in teile.items()}
    gesamt = _h({"v": SIEGEL_VERSION, "gewerbe": gewerbe_id, "jahr": jahr, "teile": {k: v["hash"] for k, v in info.items()}})
    return gesamt, info


def abschluss_zeile(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM jahr_abschluss WHERE gewerbe_id = ? AND jahr = ?", (gewerbe_id, jahr)
    ).fetchone()


def ist_abgeschlossen(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> bool:
    z = abschluss_zeile(conn, gewerbe_id, jahr)
    return bool(z and z["abgeschlossen"])


def schliessen(conn: sqlite3.Connection, gewerbe_id: int, jahr: int, email: str) -> dict:
    if ist_abgeschlossen(conn, gewerbe_id, jahr):
        raise AbschlussError(f"{jahr} ist bereits abgeschlossen.")
    if jahr >= dt.date.today().year:
        raise AbschlussError(f"{jahr} läuft noch — ein Jahr lässt sich erst nach seinem Ende abschließen.")
    s, info = siegel(conn, gewerbe_id, jahr)
    conn.execute(
        """
        INSERT INTO jahr_abschluss (gewerbe_id, jahr, abgeschlossen, abgeschlossen_am, abgeschlossen_von,
                                    siegel, siegel_info, geoeffnet_am, geoeffnet_von, geoeffnet_grund)
        VALUES (?, ?, 1, ?, ?, ?, ?, NULL, NULL, NULL)
        ON CONFLICT (gewerbe_id, jahr) DO UPDATE SET
            abgeschlossen = 1, abgeschlossen_am = excluded.abgeschlossen_am,
            abgeschlossen_von = excluded.abgeschlossen_von, siegel = excluded.siegel,
            siegel_info = excluded.siegel_info, geoeffnet_am = NULL, geoeffnet_von = NULL, geoeffnet_grund = NULL
        """,
        (gewerbe_id, jahr, jetzt_iso(), email, s, json.dumps(info)),
    )
    conn.commit()
    return {"siegel": s, "info": info}


def oeffnen(conn: sqlite3.Connection, gewerbe_id: int, jahr: int, email: str, begruendung: str) -> None:
    if not ist_abgeschlossen(conn, gewerbe_id, jahr):
        raise AbschlussError(f"{jahr} ist nicht abgeschlossen.")
    grund = " ".join((begruendung or "").split())
    if len(grund) < 5:
        raise AbschlussError("Bitte eine Begründung angeben (mindestens 5 Zeichen) — sie steht im Änderungsprotokoll.")
    conn.execute(
        "UPDATE jahr_abschluss SET abgeschlossen = 0, geoeffnet_am = ?, geoeffnet_von = ?, geoeffnet_grund = ? "
        "WHERE gewerbe_id = ? AND jahr = ?",
        (jetzt_iso(), email, grund[:500], gewerbe_id, jahr),
    )
    conn.commit()


def jahre(conn: sqlite3.Connection, gewerbe_id: int) -> list[dict]:
    """Alle Jahre mit Daten oder Abschluss (neueste zuerst) mit Status."""
    heute = dt.date.today().year
    jahre_set: set[int] = {int(r[0]) for r in conn.execute("SELECT jahr FROM euer_jahr")}
    for sql in (
        "SELECT DISTINCT CAST(substr(datum, 1, 4) AS INTEGER) FROM buchung WHERE gewerbe_id = ?",
        "SELECT DISTINCT CAST(substr(datum, 1, 4) AS INTEGER) FROM fahrt WHERE gewerbe_id = ?",
        "SELECT DISTINCT CAST(substr(anschaffungsdatum, 1, 4) AS INTEGER) FROM afa_buchung WHERE gewerbe_id = ?",
        "SELECT jahr FROM jahr_abschluss WHERE gewerbe_id = ?",
    ):
        jahre_set.update(int(r[0]) for r in conn.execute(sql, (gewerbe_id,)) if r[0])
    out = []
    for jahr in sorted((j for j in jahre_set if j <= heute), reverse=True):
        z = abschluss_zeile(conn, gewerbe_id, jahr)
        anzahl = conn.execute(
            "SELECT COUNT(*) FROM buchung WHERE gewerbe_id = ? AND substr(datum, 1, 4) = ?", (gewerbe_id, str(jahr))
        ).fetchone()[0]
        out.append(
            {
                "jahr": jahr,
                "abgeschlossen": bool(z and z["abgeschlossen"]),
                "abgeschlossen_am": z["abgeschlossen_am"] if z else None,
                "abgeschlossen_von": z["abgeschlossen_von"] if z else None,
                "siegel": z["siegel"] if z else None,
                "geoeffnet_am": z["geoeffnet_am"] if z else None,
                "geoeffnet_von": z["geoeffnet_von"] if z else None,
                "geoeffnet_grund": z["geoeffnet_grund"] if z else None,
                "anzahl_buchungen": anzahl,
                "kann_schliessen": jahr < heute,
            }
        )
    return out


def pruefen(conn: sqlite3.Connection, gewerbe_id: int) -> dict:
    """Kette des Protokolls, Schutz-Trigger und das Siegel jedes abgeschlossenen Jahres."""
    kette = kette_pruefen(conn)
    fehlen = trigger_fehlen(conn)
    ergebnis_jahre = []
    for z in conn.execute(
        "SELECT * FROM jahr_abschluss WHERE gewerbe_id = ? AND abgeschlossen = 1 ORDER BY jahr", (gewerbe_id,)
    ):
        aktuell, info = siegel(conn, gewerbe_id, z["jahr"])
        gespeichert = json.loads(z["siegel_info"] or "{}")
        abweichend = [
            ABSCHNITT_NAME[a] for a in ABSCHNITTE if gespeichert.get(a, {}).get("hash") != info[a]["hash"]
        ]
        ergebnis_jahre.append(
            {
                "jahr": z["jahr"],
                "ok": aktuell == z["siegel"],
                "abweichend": abweichend,
                "siegel": z["siegel"],
                "aktuell": aktuell,
            }
        )
    return {
        "ok": kette["ok"] and not fehlen and all(j["ok"] for j in ergebnis_jahre),
        "kette": kette,
        "trigger_fehlen": fehlen,
        "jahre": ergebnis_jahre,
    }
