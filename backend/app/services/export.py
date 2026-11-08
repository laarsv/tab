"""EÜR-Export: Summenblatt (je befüllte Zeile eine Summe) + Beleg-Journal (CSV).

- Bewirtung & Co.: abzug_quote wird je Kategorie-Summe angewandt, dann auf
  Zeilen-Ebene aggregiert, am Ende auf Cent gerundet.
- AfA fließt als Jahres-AfA-Betrag in die Zeile der Kategorie `afa_beweglich`
  (2025: Zeile 33, 2026: Zeile 34; services/afa.py).
- Guard: fehlt ein Mapping fürs angeforderte Jahr -> MappingMissingError (klare
  Fehlermeldung statt Crash). Nie befüllte Zeilen werden je Jahr defensiv geprüft
  (`seed.nie_befuellt`).
- CSV-Dialekt: deutsch/Excel — Semikolon, Komma-Dezimal, UTF-8-BOM, Datum TT.MM.JJJJ.
"""
from __future__ import annotations

import csv
import datetime
import hashlib
import io
import os
import sqlite3
import zipfile

from .afa import afa_jahr, methode_text
from .privatanteil import betrieblich_cent
from ..config import settings
from ..seed import nie_befuellt


class MappingMissingError(Exception):
    """Für das angeforderte Jahr existiert kein EÜR-Mapping."""


class BesteuerungNotSupportedError(Exception):
    """Export ist aktuell nur für Kleinunternehmer (§19) verfügbar."""


def format_cent_de(cent: int) -> str:
    """123456 -> '1234,56' (Komma-Dezimal, kein Tausendertrenner — re-importfreundlich)."""
    sign = "-" if cent < 0 else ""
    v = abs(int(cent))
    return f"{sign}{v // 100},{v % 100:02d}"


def _prozent_de(bp: int) -> str:
    """Basispunkte als deutsche Prozentzahl: 2000 -> '20', 3333 -> '33,33'."""
    text = f"{bp / 100:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _date_de(iso: str) -> str:
    """'2025-03-07' -> '07.03.2025'."""
    return f"{iso[8:10]}.{iso[5:7]}.{iso[0:4]}"


def _gewerbe_or_404(conn: sqlite3.Connection, gewerbe_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    if row is None:
        raise MappingMissingError(f"Gewerbe {gewerbe_id} existiert nicht.")
    return row


def build_summenblatt(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> dict:
    gewerbe = _gewerbe_or_404(conn, gewerbe_id)

    if gewerbe["besteuerung"] != "kleinunternehmer":
        raise BesteuerungNotSupportedError(
            "Der EÜR-Export ist aktuell nur für Kleinunternehmer (§19 UStG) verfügbar. "
            "Dieses Gewerbe ist auf Regelbesteuerung gesetzt."
        )

    jahr_meta = conn.execute("SELECT * FROM euer_jahr WHERE jahr = ?", (jahr,)).fetchone()
    mapping_rows = conn.execute(
        "SELECT kategorie_id, zeile_nummer FROM euer_mapping WHERE jahr = ?", (jahr,)
    ).fetchall()
    if jahr_meta is None or not mapping_rows:
        raise MappingMissingError(
            f"Für das Jahr {jahr} ist kein EÜR-Mapping hinterlegt. "
            f"Verfügbar sind aktuell nur die geseedeten Jahrgänge."
        )

    mapping = {r["kategorie_id"]: r["zeile_nummer"] for r in mapping_rows}
    labels = {
        r["nummer"]: r["bezeichnung"]
        for r in conn.execute("SELECT nummer, bezeichnung FROM euer_zeile WHERE jahr = ?", (jahr,))
    }
    kategorien = {
        r["id"]: r for r in conn.execute("SELECT id, name, typ, abzug_quote FROM kategorie")
    }

    # Summen je Zeile: zuerst je Kategorie roh summieren, Quote anwenden, dann je Zeile.
    zeile_cent: dict[int, int] = {}
    zeile_typ: dict[int, str] = {}

    roh_je_kat: dict[int, int] = {}
    for r in conn.execute(
        "SELECT p.kategorie_id, p.betrag_cent, p.privat_bp FROM buchung_position p "
        "JOIN buchung b ON b.id = p.buchung_id "
        "WHERE b.gewerbe_id = ? AND substr(b.datum,1,4) = ?",
        (gewerbe_id, str(jahr)),
    ):
        # Nur der betriebliche Teil zählt (Privatanteil bei Ausgaben, services/privatanteil.py)
        betrieblich = betrieblich_cent(r["betrag_cent"], r["privat_bp"])
        roh_je_kat[r["kategorie_id"]] = roh_je_kat.get(r["kategorie_id"], 0) + betrieblich

    for kat_id, roh in roh_je_kat.items():
        if kat_id not in mapping:
            # Stiller Wegfall wäre ein falsches Summenblatt — lieber klarer Fehler.
            raise MappingMissingError(
                f"Kategorie „{kategorien[kat_id]['name']}“ hat kein EÜR-Mapping für {jahr}. "
                f"Mapping in seed.py ergänzen und neu deployen."
            )
        kat = kategorien[kat_id]
        effektiv = round(roh * kat["abzug_quote"])
        nummer = mapping[kat_id]
        zeile_cent[nummer] = zeile_cent.get(nummer, 0) + effektiv
        zeile_typ[nummer] = kat["typ"]

    # AfA -> Jahres-AfA-Betrag in die jeweilige (ist_afa-)Zeile.
    for r in conn.execute(
        "SELECT kategorie_id, anschaffungskosten_cent, anschaffungsdatum, "
        "nutzungsdauer_jahre, abgang_datum, afa_methode, degressiv_bp, linear_ab_jahr "
        "FROM afa_buchung WHERE gewerbe_id = ?",
        (gewerbe_id,),
    ):
        if r["kategorie_id"] not in mapping:
            raise MappingMissingError(
                f"AfA-Kategorie „{kategorien[r['kategorie_id']]['name']}“ hat kein "
                f"EÜR-Mapping für {jahr}. Mapping in seed.py ergänzen und neu deployen."
            )
        betrag = afa_jahr(r, jahr)
        if betrag <= 0:
            continue
        nummer = mapping[r["kategorie_id"]]
        zeile_cent[nummer] = zeile_cent.get(nummer, 0) + betrag
        zeile_typ[nummer] = "ausgabe"

    zeilen = []
    summe_einnahmen = 0
    summe_ausgaben = 0
    for nummer in sorted(zeile_cent):
        betrag = zeile_cent[nummer]
        if betrag == 0:
            continue
        if nummer in nie_befuellt(jahr):
            raise ValueError(f"Zeile {nummer} darf bei Kleinunternehmern nie befüllt werden.")
        typ = zeile_typ[nummer]
        zeilen.append(
            {
                "nummer": nummer,
                "bezeichnung": labels.get(nummer, f"Zeile {nummer}"),
                "typ": typ,
                "betrag_cent": betrag,
            }
        )
        if typ == "einnahme":
            summe_einnahmen += betrag
        else:
            summe_ausgaben += betrag

    return {
        "gewerbe": {
            "id": gewerbe["id"],
            "name": gewerbe["name"],
            "steuernummer": gewerbe["steuernummer"],
            "besteuerung": gewerbe["besteuerung"],
        },
        "kleinunternehmer": True,
        "jahr": jahr,
        "vorlaeufig": bool(jahr_meta["vorlaeufig"]),
        "quelle": jahr_meta["quelle"],
        "zeilen": zeilen,
        "summe_einnahmen_cent": summe_einnahmen,
        "summe_ausgaben_cent": summe_ausgaben,
        "gewinn_cent": summe_einnahmen - summe_ausgaben,
    }


def _csv_to_bytes(rows: list[list[str]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerows(rows)
    return ("﻿" + buf.getvalue()).encode("utf-8")  # BOM für Excel


def summenblatt_csv(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> bytes:
    data = build_summenblatt(conn, gewerbe_id, jahr)
    rows: list[list[str]] = [
        ["EÜR-Summenblatt"],
        ["Gewerbe", data["gewerbe"]["name"]],
        ["Steuernummer", data["gewerbe"]["steuernummer"] or ""],
        ["Kleinunternehmer §19 UStG", "ja"],
        ["Jahr", str(jahr)],
    ]
    if data["vorlaeufig"]:
        rows.append(["Hinweis", "Vorläufiges Mapping — vor Steuersaison gegen Vordruck abgleichen"])
    rows += [
        [],
        ["Zeile", "Bezeichnung", "Betrag (EUR)"],
    ]
    for z in data["zeilen"]:
        rows.append([str(z["nummer"]), z["bezeichnung"], format_cent_de(z["betrag_cent"])])
    rows += [
        [],
        ["", "Summe Betriebseinnahmen (Zeile 23)", format_cent_de(data["summe_einnahmen_cent"])],
        ["", "Summe Betriebsausgaben", format_cent_de(data["summe_ausgaben_cent"])],
        ["", "Gewinn / Verlust", format_cent_de(data["gewinn_cent"])],
    ]
    return _csv_to_bytes(rows)


def journal_csv(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> bytes:
    gewerbe = _gewerbe_or_404(conn, gewerbe_id)
    if gewerbe["besteuerung"] != "kleinunternehmer":
        raise BesteuerungNotSupportedError(
            "Der Export ist aktuell nur für Kleinunternehmer (§19 UStG) verfügbar."
        )
    jahr_meta = conn.execute("SELECT * FROM euer_jahr WHERE jahr = ?", (jahr,)).fetchone()
    mapping_rows = conn.execute(
        "SELECT kategorie_id, zeile_nummer FROM euer_mapping WHERE jahr = ?", (jahr,)
    ).fetchall()
    if jahr_meta is None or not mapping_rows:
        raise MappingMissingError(f"Für das Jahr {jahr} ist kein EÜR-Mapping hinterlegt.")
    mapping = {r["kategorie_id"]: r["zeile_nummer"] for r in mapping_rows}

    rows: list[list[str]] = [
        [
            "Datum",
            "Gewerbe",
            "Kategorie",
            "EÜR-Zeile",
            "Betrag brutto (EUR)",
            "Abzug %",
            "Beschreibung",
            "Beleg-Details",
            "Privatanteil %",
            "Betrieblicher Betrag (EUR)",
        ]
    ]

    for r in conn.execute(
        """
        SELECT b.datum, p.betrag_cent, p.privat_bp, b.beschreibung, p.beleg_details,
               p.kategorie_id, k.name AS kat_name, k.abzug_quote
        FROM buchung_position p
        JOIN buchung b ON b.id = p.buchung_id
        JOIN kategorie k ON k.id = p.kategorie_id
        WHERE b.gewerbe_id = ? AND substr(b.datum,1,4) = ?
        ORDER BY b.datum, b.id, p.id
        """,
        (gewerbe_id, str(jahr)),
    ):
        zeile = mapping.get(r["kategorie_id"], "")
        rows.append(
            [
                _date_de(r["datum"]),
                gewerbe["name"],
                r["kat_name"],
                str(zeile),
                format_cent_de(r["betrag_cent"]),
                str(round(r["abzug_quote"] * 100)),
                r["beschreibung"] or "",
                r["beleg_details"] or "",
                _prozent_de(r["privat_bp"]) if r["privat_bp"] else "",
                format_cent_de(betrieblich_cent(r["betrag_cent"], r["privat_bp"])),
            ]
        )

    # AfA als eigene Zeilen (Jahres-AfA-Betrag).
    for r in conn.execute(
        """
        SELECT a.anschaffungskosten_cent, a.anschaffungsdatum, a.nutzungsdauer_jahre,
               a.abgang_datum, a.afa_methode, a.degressiv_bp, a.linear_ab_jahr,
               a.bezeichnung, a.kategorie_id, k.name AS kat_name
        FROM afa_buchung a JOIN kategorie k ON k.id = a.kategorie_id
        WHERE a.gewerbe_id = ?
        ORDER BY a.anschaffungsdatum, a.id
        """,
        (gewerbe_id,),
    ):
        betrag = afa_jahr(r, jahr)
        if betrag <= 0:
            continue
        zeile = mapping.get(r["kategorie_id"], "")
        rows.append(
            [
                f"31.12.{jahr}",
                gewerbe["name"],
                r["kat_name"],
                str(zeile),
                format_cent_de(betrag),
                "100",
                f"Jahres-AfA {r['bezeichnung']} (Anschaffung {_date_de(r['anschaffungsdatum'])}, "
                + (f"ND {r['nutzungsdauer_jahre']} J." if r["afa_methode"] in (None, "linear") else methode_text(r))
                + (f", Abgang {_date_de(r['abgang_datum'])}" if r["abgang_datum"] else "")
                + ")",
                "",
                "",
                format_cent_de(betrag),
            ]
        )

    return _csv_to_bytes(rows)


def protokoll_csv(conn: sqlite3.Connection, gewerbe_id: int) -> bytes:
    """Änderungsprotokoll des Gewerbes (alle Einträge, in der Reihenfolge der Hash-Kette)."""
    rows = [["Nr", "Zeitpunkt (UTC)", "Nutzer", "Tabelle", "Zeile", "Aktion", "Vorher", "Nachher",
             "Vorgaenger-Hash", "Hash"]]
    for r in conn.execute("SELECT * FROM audit_log WHERE gewerbe_id = ? ORDER BY id", (gewerbe_id,)):
        rows.append([
            str(r["id"]), r["ts"], r["actor"] or "", r["tabelle"], str(r["zeile_id"]), r["aktion"],
            r["vorher"] or "", r["nachher"] or "", r["prev_hash"] or "", r["row_hash"] or "",
        ])
    return _csv_to_bytes(rows)


LIESMICH = """Jahresarchiv {jahr} - {gewerbe}
Erstellt am {erstellt} (UTC) mit Tab.

Inhalt
  euer-summenblatt-{jahr}.csv     EUeR-Summenblatt je Anlage-EUeR-Zeile
  beleg-journal-{jahr}.csv        Beleg-Journal
  fahrten-{jahr}.csv              Fahrten-Liste (nur wenn vorhanden)
  belege/                         Beleg-Dateien der Buchungen des Jahres
  protokoll/aenderungsprotokoll.csv   Aenderungsprotokoll des Gewerbes (Hash-Kette)
  protokoll/pruefwert.txt         Kopf der Hash-Kette und Siegel des Jahres - bitte AUSSERHALB des
                                  Servers aufbewahren (z. B. zusammen mit diesem Archiv)
  pruefsummen.sha256              SHA-256 jeder anderen Datei im Archiv

Pruefen (Linux/macOS, im entpackten Ordner):
  sha256sum -c pruefsummen.sha256      (macOS: shasum -a 256 -c pruefsummen.sha256)

Hinweis: Die Pruefsummen zeigen, dass die Dateien seit dem Erstellen des Archivs unveraendert sind.
Sie ersetzen weder eine Steuerberatung noch eine Zertifizierung.
"""


def belege_zip(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> bytes:
    """Jahres-Archiv: Summenblatt + Journal (CSV) + alle Beleg-Dateien der Buchungen des Jahres,
    dazu Änderungsprotokoll, Prüfwert und `pruefsummen.sha256` (SHA-256 jeder Datei).
    Dateiname je Beleg: belege/JJJJ-MM-TT_id_originalname."""
    buf = io.BytesIO()
    fehlend: list[str] = []
    summen: dict[str, str] = {}

    def schreibe(zf: zipfile.ZipFile, arcname: str, data: bytes) -> None:
        zf.writestr(arcname, data)
        summen[arcname] = hashlib.sha256(data).hexdigest()

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        schreibe(zf, f"euer-summenblatt-{jahr}.csv", summenblatt_csv(conn, gewerbe_id, jahr))
        schreibe(zf, f"beleg-journal-{jahr}.csv", journal_csv(conn, gewerbe_id, jahr))
        # Fahrten-Liste (Nachweis für die km-Pauschale), falls vorhanden.
        fahrten = conn.execute(
            "SELECT datum, ziel, anlass, km FROM fahrt "
            "WHERE gewerbe_id = ? AND substr(datum,1,4) = ? ORDER BY datum, id",
            (gewerbe_id, str(jahr)),
        ).fetchall()
        if fahrten:
            rows = [["Datum", "Ziel/Strecke", "Anlass", "km"]]
            summe_km = 0.0
            for f in fahrten:
                rows.append([_date_de(f["datum"]), f["ziel"], f["anlass"] or "", str(f["km"]).replace(".", ",")])
                summe_km += f["km"]
            rows.append([])
            rows.append(["", "", "Summe km", str(round(summe_km, 1)).replace(".", ",")])
            rows.append(["", "", "× 0,30 €/km", format_cent_de(round(summe_km * 30))])
            schreibe(zf, f"fahrten-{jahr}.csv", _csv_to_bytes(rows))
        for r in conn.execute(
            """
            SELECT bel.*, b.datum FROM beleg bel
            JOIN buchung b ON b.id = bel.buchung_id
            WHERE bel.gewerbe_id = ? AND substr(b.datum,1,4) = ?
            ORDER BY b.datum, bel.id
            """,
            (gewerbe_id, str(jahr)),
        ):
            path = os.path.join(settings.UPLOAD_ROOT, r["stored_name"])
            arcname = f"belege/{r['datum']}_{r['id']}_{r['original_name']}"
            if os.path.exists(path):
                with open(path, "rb") as fh:
                    schreibe(zf, arcname, fh.read())
            else:
                fehlend.append(arcname)
        if fehlend:
            schreibe(
                zf,
                "fehlende-dateien.txt",
                (
                    "Diese Belege sind in der Datenbank erfasst, die Datei fehlt aber:\n" + "\n".join(fehlend)
                ).encode("utf-8"),
            )

        # Änderungsprotokoll + Prüfwert (Kopf der Hash-Kette zum Aufbewahren außerhalb des Servers)
        jetzt = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        schreibe(zf, "protokoll/aenderungsprotokoll.csv", protokoll_csv(conn, gewerbe_id))
        kopf = conn.execute("SELECT id, row_hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        zeilen = [f"Erstellt (UTC): {jetzt}"]
        if kopf:
            zeilen.append(f"Änderungsprotokoll: Nr. {kopf['id']} · {kopf['row_hash']}")
        abschluss = conn.execute(
            "SELECT * FROM jahr_abschluss WHERE gewerbe_id = ? AND jahr = ?", (gewerbe_id, jahr)
        ).fetchone()
        if abschluss and abschluss["abgeschlossen"]:
            zeilen.append(
                f"{jahr}: abgeschlossen am {abschluss['abgeschlossen_am']} von {abschluss['abgeschlossen_von']}, "
                f"Siegel {abschluss['siegel']}"
            )
        else:
            zeilen.append(f"{jahr}: noch nicht abgeschlossen")
        schreibe(zf, "protokoll/pruefwert.txt", ("\n".join(zeilen) + "\n").encode("utf-8"))
        gname = conn.execute("SELECT name FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
        schreibe(
            zf,
            "LIESMICH.txt",
            LIESMICH.format(jahr=jahr, gewerbe=gname["name"] if gname else "", erstellt=jetzt).encode("utf-8"),
        )
        # Prüfsummen zuletzt, im Format von sha256sum (zwei Leerzeichen)
        zf.writestr(
            "pruefsummen.sha256",
            "".join(f"{h}  {name}\n" for name, h in sorted(summen.items())).encode("utf-8"),
        )
    return buf.getvalue()


def backup_zip(conn: sqlite3.Connection) -> bytes:
    """Komplett-Backup: konsistenter SQLite-Snapshot (backup API) + alle Upload-Dateien."""
    import tempfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        with tempfile.TemporaryDirectory() as td:
            snap_path = os.path.join(td, "tab.db")
            snap = sqlite3.connect(snap_path)
            try:
                conn.backup(snap)
            finally:
                snap.close()
            zf.write(snap_path, "tab.db")
        if os.path.isdir(settings.UPLOAD_ROOT):
            for name in sorted(os.listdir(settings.UPLOAD_ROOT)):
                path = os.path.join(settings.UPLOAD_ROOT, name)
                if os.path.isfile(path):
                    zf.write(path, f"uploads/{name}")
    return buf.getvalue()
