"""Einmaliger Umzug aus Lexware Office (DATEV-Export) nach Tab — Kommandozeile im Backend-Container.

    python -m app.lexware_import --ordner /pfad/entpackt --gewerbe 2 --email inhaber@… [--abschliessen-bis 2024]
                                 [--ausfuehren]

Ohne `--ausfuehren` ist es ein Probelauf: rechnet alles, schreibt nichts und gibt die Jahressummen je Kategorie und
die Hinweise aus. Erwartet den Ordner mit den entpackten Lexware-Exporten (je Jahr „DATEV-Export_von_…“ mit
EXTF_Buchungsstapel/Sachkonten, „DATEV-Export_Belegbilder_von_…“ mit document.xml + PDFs, „Kontoumsätze-Girokonten_von_…“
und Kontakte.csv). Ablauf und Regeln: services/datev_import.py.
"""
from __future__ import annotations

import argparse
import collections
import csv
import difflib
import glob
import io
import os
import re
import sys

from .db import _connect
from .services import datev_import as di


def _jahr(pfad: str) -> int:
    return int(re.search(r"von_(\d{4})", pfad).group(1))


def _sachkonten(ordner: str) -> dict[str, str]:
    namen = {}
    for f in glob.glob(os.path.join(ordner, "DATEV-Export_von_*", "EXTF_Sachkonten_*.csv")):
        rows = list(csv.reader(io.StringIO(open(f, "rb").read().decode("cp1252")), delimiter=";"))
        for r in rows[2:]:
            if r and r[0]:
                namen[r[0].lstrip("0")] = r[1].strip()
    return namen


def _konto_iban(ordner: str, sachkonten: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Bank-Sachkonto → IBAN über die Namen der Kontoumsatz-Dateien („…_<IBAN>_<Name>_von_…“)."""
    dateinamen = {}
    for f in glob.glob(os.path.join(ordner, "Kontoumsätze-Girokonten_*", "*.csv")):
        m = re.search(r"Kontoumsätze_([A-Z]{2}\d{2}[A-Z0-9]+)_(.+?)_von_", os.path.basename(f))
        if m:
            dateinamen[m.group(1)] = m.group(2).replace("-", " ")
    zuordnung, namen = {}, {}
    for konto, label in sachkonten.items():
        if not (1200 <= int(konto) <= 1299):
            continue
        best = max(dateinamen.items(), key=lambda kv: difflib.SequenceMatcher(None, label.lower(), kv[1].lower()).ratio(),
                   default=None)
        if best and difflib.SequenceMatcher(None, label.lower(), best[1].lower()).ratio() >= 0.6:
            zuordnung[konto] = best[0]
            namen[best[0]] = label
    return zuordnung, namen


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ordner", required=True)
    ap.add_argument("--gewerbe", type=int, required=True)
    ap.add_argument("--email", required=True)
    ap.add_argument("--abschliessen-bis", type=int, default=None)
    ap.add_argument("--offen-ab", default=None, help="Bankumsätze vor diesem Tag ohne Zuordnung als Altbestand ignorieren")
    ap.add_argument("--umkontieren", action="append", default=[],
                    help="KONTO=KATEGORIE:AB_JAHR, z. B. 320=kfz_kosten:2025 (Leasing auf dem Anlagenkonto)")
    ap.add_argument("--anlagen", help="JSON mit den Anlagen zum Stichtag (siehe datev_import.anlagen_uebernehmen)")
    ap.add_argument("--anlagen-stichtag", default=None)
    ap.add_argument("--herkunft-nachtragen", action="store_true",
                    help="nur einmal: Schlüssel eines Imports von vor v40 nachtragen (gleiche Dateien und Optionen)")
    ap.add_argument("--ausfuehren", action="store_true")
    a = ap.parse_args(argv)

    for u in a.umkontieren:
        konto, rest = u.split("=")
        kat, ab = rest.split(":")
        di.UMKONTIEREN[konto] = (int(ab), kat, f"(bei Lexware auf Konto {konto} gebucht)")
    zeilen = []
    for f in sorted(glob.glob(os.path.join(a.ordner, "DATEV-Export_von_*", "EXTF_Buchungsstapel_*.csv"))):
        zeilen += di.lesen(open(f, "rb").read(), _jahr(f))
    buchungen, bericht = di.plan(zeilen)
    dateien = {}
    for f in glob.glob(os.path.join(a.ordner, "DATEV-Export_Belegbilder_*", "*.pdf")):
        dateien[os.path.basename(f)[:-4]] = f
    sachkonten = _sachkonten(a.ordner)
    konto_iban, kontonamen = _konto_iban(a.ordner, sachkonten)
    umsaetze = []
    for f in sorted(glob.glob(os.path.join(a.ordner, "Kontoumsätze-Girokonten_*", "*.csv"))):
        umsaetze += di.umsaetze_lesen(open(f, "rb").read())

    print("Sammelzahlungen zusammengeführt:", di.sammelzahlungen(buchungen, konto_iban, umsaetze))

    # Bericht
    summen = collections.defaultdict(lambda: collections.defaultdict(int))
    for b in buchungen:
        for k, v in b.positionen.items():
            summen[b.datum[:4]][k] += v
    print(f"{len(zeilen)} Lexware-Zeilen → {len(buchungen)} Buchungen, {len(dateien)} Belegdateien, {len(umsaetze)} Kontoumsätze")
    print("Bankkonten:", {k: (sachkonten.get(k), v) for k, v in konto_iban.items()})
    for j in sorted(summen):
        ein = sum(v for k, v in summen[j].items() if k in di.EINNAHMEN)
        aus = sum(v for k, v in summen[j].items() if k not in di.EINNAHMEN)
        print(f"  {j}: Einnahmen {ein / 100:>12,.2f}  Ausgaben {aus / 100:>12,.2f}  Überschuss {(ein - aus) / 100:>12,.2f}"
              "  (ohne AfA)")
    for k, v in bericht.items():
        print(f"  {k}: {len(v)}")

    conn = _connect(actor=a.email)
    g = conn.execute("SELECT * FROM gewerbe WHERE id = ?", (a.gewerbe,)).fetchone()
    if g is None or g["owner_email"] != a.email:
        print("Gewerbe gehört nicht zu dieser E-Mail.", file=sys.stderr)
        return 2
    bekannt = {r["schluessel"] for r in conn.execute(
        "SELECT schluessel FROM fremd_import WHERE gewerbe_id = ? AND quelle = 'lexware'", (a.gewerbe,))}
    schon_importiert = conn.execute(
        "SELECT 1 FROM beleg WHERE gewerbe_id = ? AND original_name LIKE 'Lexware %'", (a.gewerbe,)).fetchone()
    if a.herkunft_nachtragen:
        return herkunft_nachtragen(conn, a, zeilen, buchungen, a.ausfuehren)
    if schon_importiert and not bekannt:
        print("Für dieses Gewerbe wurde schon importiert, aber ohne Schlüssel — erst --herkunft-nachtragen.", file=sys.stderr)
        return 2

    # Nachimport: nur Buchungen, deren Lexware-Zeilen noch unbekannt sind; Belege nur, wenn noch nicht übernommen
    ref_schluessel = {z.ref: z.schluessel for z in zeilen}
    if bekannt:
        neu, gemischt = [], []
        for b in buchungen:
            alt = [r for r in b.zeilen if ref_schluessel[r] in bekannt]
            (neu if not alt else gemischt if len(alt) < len(b.zeilen) else []).append(b)
        print(f"Nachimport: {len(neu)} neue Buchungen, {len(gemischt)} teils schon übernommen (ausgelassen, bitte prüfen)")
        for b in gemischt:
            print("   teils bekannt:", b.datum, b.text[:60], b.positionen)
        buchungen = neu
        dateien = {g: p for g, p in dateien.items() if f"guid:{g}" not in bekannt}
    if not a.ausfuehren:
        print("Probelauf — nichts geschrieben.")
        return 0

    try:
        erg = di.ausfuehren(conn, gewerbe_id=a.gewerbe, buchungen=buchungen, dateien=dateien)
        _herkunft_speichern(conn, a.gewerbe, zeilen, bekannt, erg["ref"], erg["guids"])
        print({k: v for k, v in erg.items() if k not in ("ref", "guids")})
        bz = di.bank_zeilen(zeilen, konto_iban, erg["ref"])
        bank = di.bank_importieren(
            conn, gewerbe_id=a.gewerbe, umsaetze=umsaetze, bzeilen=bz, ref_buchung=erg["ref"], kontonamen=kontonamen,
            rechnungsgruppe=di.rechnungsgegenkonten(zeilen), offen_ab=a.offen_ab or "0000", email=a.email,
        )
        print("Bank:", bank)
        k = kontakte(conn, a.gewerbe, a.ordner)
        print("Kontakte:", k)
        if a.anlagen:
            import json
            print("Anlagen:", di.anlagen_uebernehmen(conn, gewerbe_id=a.gewerbe, anlagen=json.load(open(a.anlagen)),
                                                     stichtag=a.anlagen_stichtag))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    if a.abschliessen_bis:
        from .services import abschluss
        jahre = sorted({int(b.datum[:4]) for b in buchungen if int(b.datum[:4]) <= a.abschliessen_bis})
        for j in jahre:
            abschluss.schliessen(conn, a.gewerbe, j, a.email)
            conn.execute(
                "INSERT INTO frist_erledigt (email, schluessel, erledigt_am) VALUES (?, ?, date('now')) "
                "ON CONFLICT(email, schluessel) DO NOTHING", (a.email, f"steuererklaerung:{j}"))
        conn.commit()
        print("Abgeschlossen:", jahre)
    return 0


def _herkunft_speichern(conn, gewerbe_id: int, zeilen, bekannt: set[str], ref_buchung: dict, guids: dict) -> None:
    for z in zeilen:
        if z.schluessel not in bekannt:
            conn.execute("INSERT OR IGNORE INTO fremd_import (gewerbe_id, quelle, schluessel, buchung_id) VALUES (?, 'lexware', ?, ?)",
                         (gewerbe_id, z.schluessel, ref_buchung.get(z.ref)))
    for g, bid in guids.items():
        conn.execute("INSERT OR IGNORE INTO fremd_import (gewerbe_id, quelle, schluessel, buchung_id) VALUES (?, 'lexware', ?, ?)",
                     (gewerbe_id, f"guid:{g}", bid))


def herkunft_nachtragen(conn, a, zeilen, buchungen, schreiben: bool) -> int:
    """Für einen Import von vor v40: die damals angelegten Buchungen in derselben Reihenfolge wiederfinden (fortlaufende
    IDs ab der ersten) und die Schlüssel nachtragen. Bricht ab, wenn auch nur eine Buchung nicht passt."""
    erste = buchungen[0]
    kand = conn.execute(
        "SELECT id FROM buchung WHERE gewerbe_id = ? AND datum = ? AND beschreibung LIKE ? ORDER BY id",
        (a.gewerbe, erste.datum, erste.text[:200].replace("%", "_") + "%")).fetchall()
    for k in kand:
        start = k["id"]
        ok = True
        for i, b in enumerate(buchungen):
            r = conn.execute("SELECT datum, beschreibung FROM buchung WHERE id = ? AND gewerbe_id = ?", (start + i, a.gewerbe)).fetchone()
            if r is None or r["datum"] != b.datum or not (r["beschreibung"] or "").startswith(b.text[:200]):
                ok = False
                break
        if ok:
            ref = {}
            for i, b in enumerate(buchungen):
                for z in b.zeilen:
                    ref[z] = start + i
            guids = {}
            # Belege: je Buchung die GUIDs, die beim Import an ihr hingen (erste Buchung je GUID)
            vergeben = set()
            for i, b in enumerate(buchungen):
                for g in b.guids:
                    if g not in vergeben:
                        vergeben.add(g)
                        guids[g] = start + i
            print(f"Gefunden: Buchungen {start}–{start + len(buchungen) - 1}, {len(guids)} Belege")
            if schreiben:
                _herkunft_speichern(conn, a.gewerbe, zeilen, set(), ref, guids)
                conn.commit()
                print("Schlüssel nachgetragen:", conn.execute(
                    "SELECT COUNT(*) FROM fremd_import WHERE gewerbe_id = ?", (a.gewerbe,)).fetchone()[0])
            return 0
    print("Die importierten Buchungen ließen sich nicht eindeutig wiederfinden — nichts nachgetragen.", file=sys.stderr)
    return 2


def kontakte(conn, gewerbe_id: int, ordner: str) -> dict:
    """Kunden aus Kontakte.csv (Lexware) als Rechnungsempfänger; Lieferanten bleiben weg."""
    pfad = next(iter(glob.glob(os.path.join(ordner, "Kontakte*.csv"))), None)
    if not pfad:
        return {"datei": None}
    text = open(pfad, "rb").read().decode("utf-8-sig")
    neu = vorhanden = 0
    for r in csv.DictReader(io.StringIO(text), delimiter=";"):
        if not (r.get("Kundennummer") or "").strip():
            continue
        name = (r.get("Firmenname") or "").strip() or " ".join(
            x for x in ((r.get("Vorname") or "").strip(), (r.get("Nachname") or "").strip()) if x)
        if not name:
            continue
        zeilen = [r.get("Straße (Rechnungsadresse 1)", ""), r.get("Adresszusatz (Rechnungsadresse 1)", ""),
                  " ".join(x for x in (r.get("PLZ (Rechnungsadresse 1)", ""), r.get("Ort (Rechnungsadresse 1)", "")) if x)]
        anschrift = "\n".join([name] + [z.strip() for z in zeilen if z and z.strip()])
        email = next((v.strip() for k, v in r.items() if k and "mail" in k.lower() and v and "@" in v), None)
        notiz = f"Lexware-Kundennummer {r['Kundennummer'].strip()}"
        cur = conn.execute(
            "INSERT INTO kontakt (gewerbe_id, name, anschrift, email, notiz) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(gewerbe_id, name) DO NOTHING", (gewerbe_id, name[:120], anschrift, email, notiz))
        if cur.rowcount:
            neu += 1
        else:
            vorhanden += 1
    return {"neu": neu, "schon_da": vorhanden}


if __name__ == "__main__":
    raise SystemExit(main())
