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
    if conn.execute("SELECT 1 FROM beleg WHERE gewerbe_id = ? AND original_name LIKE 'Lexware %'", (a.gewerbe,)).fetchone():
        print("Für dieses Gewerbe wurde schon aus Lexware importiert — Abbruch.", file=sys.stderr)
        return 2
    if not a.ausfuehren:
        print("Probelauf — nichts geschrieben.")
        return 0

    try:
        erg = di.ausfuehren(conn, gewerbe_id=a.gewerbe, buchungen=buchungen, dateien=dateien)
        print({k: v for k, v in erg.items() if k != "ref"})
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
