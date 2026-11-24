"""Import aus einem DATEV-Buchungsstapel (EXTF, SKR03) — z. B. dem DATEV-Export von Lexware Office — in Tab.

Lexware und DATEV buchen doppelt und über Personenkonten: erst die Rechnung (Aufwand an Kreditor bzw. Debitor an
Erlös), später die Zahlung (Kreditor an Bank bzw. Bank an Debitor). Tab bucht die EÜR nach dem Zahlungsfluss. Der Import
rechnet deshalb jede Zahlung auf die Konten ihrer Rechnung um:

  * Rechnung und Zahlung gehören zusammen, wenn Personenkonto und Belegfeld 1 übereinstimmen (über alle Jahre). Je
    Zahlungstag und Geldkonto entsteht eine Tab-Buchung; ihre Positionen verteilen den Zahlbetrag anteilig auf die (um
    Korrekturen/Storni bereinigten) Konten der Rechnung.
  * Ergebniskonto direkt gegen Geld (Bank, Geldtransit 1360, Verrechnung 1371, Privat 1800/1880/1890) → Buchung an
    dem Tag (Zeilen mit demselben Beleg am selben Tag werden eine Buchung).
  * Lohnaufwand gegen Lohnverbindlichkeiten (17xx) → Buchung am Tag der Lohnverbuchung (die Auszahlung folgt meist im
    selben Monat; über den Jahreswechsel kann sich das um Tage verschieben).
  * Nicht übernommen (in Tab keine Betriebseinnahme/-ausgabe): Abschreibungen 4830/4855 (Tab rechnet die AfA selbst
    aus den Anlagen), Anlagenzugänge 0420/0490 (→ Anlagen), Pkw 0320, Gewerbesteuer 4320, Privates (18xx),
    Geldtransit, durchlaufende Posten, Forderungsausfälle, Lohnverbindlichkeiten.
  * Tab kennt keine negativen Beträge: eine Minderung von Einnahmen (z. B. Provisionsrückzahlung) wird eine Ausgabe
    „Fremdleistungen/Provisionen“, eine Erstattung von Ausgaben eine Einnahme — der Gewinn bleibt gleich.

`lesen()` + `plan()` lesen nur; `ausfuehren()` schreibt Buchungen und Belege, `bank_importieren()` die Kontoumsätze
(Lexware „Kontoumsätze“, DATEV-ASCII) und verknüpft sie mit den Buchungen.
"""
from __future__ import annotations

import collections
import csv
import dataclasses
import datetime as dt
import hashlib
import io
import os
import re
import sqlite3
import uuid

from ..config import settings

# SKR03-Konto → Tab-Kategorie (None = bewusst nicht übernehmen)
KONTEN: dict[str, str | None] = {
    "3100": "fremdleistungen",
    "4100": "personal", "4120": "personal", "4130": "personal", "4138": "personal", "4140": "personal",
    "4144": "personal", "4194": "personal", "4195": "personal", "2749": "personal",
    "4210": "miete_raeume", "4250": "grundstueck_sonstige", "4260": "grundstueck_sonstige",
    "4360": "versicherungen_betrieb", "4380": "versicherungen_betrieb",
    "4520": "kfz_kosten", "4530": "kfz_kosten", "4540": "kfz_kosten", "4550": "kfz_kosten", "4560": "kfz_kosten",
    "4570": "kfz_kosten", "4580": "kfz_kosten", "4595": "kfz_kosten",
    "4600": "werbung_repraesentation", "4640": "werbung_repraesentation", "4630": "geschenke",
    "4650": "bewirtung", "4654": "bewirtung", "4653": "buerobedarf",
    "4660": "reise_nebenkosten", "4666": "reise_nebenkosten", "4670": "reise_nebenkosten", "4676": "reise_nebenkosten",
    "4673": "oepnv", "4674": "verpflegungsmehraufwand",
    "4900": "buerobedarf", "4910": "buerobedarf", "4930": "buerobedarf", "4940": "buerobedarf", "4980": "buerobedarf",
    "4985": "buerobedarf", "2309": "buerobedarf",
    "4920": "telekommunikation", "4925": "telekommunikation",
    "4945": "fortbildung", "4946": "fortbildung",
    "4950": "rechts_steuer_buchfuehrung", "4955": "rechts_steuer_buchfuehrung", "4957": "rechts_steuer_buchfuehrung",
    "4964": "software_hosting", "4970": "kontogebuehren",
    "480": "gwg",
    "8195": "einnahme_ku", "8200": "einnahme_ku", "2660": "einnahme_ku", "8700": "einnahme_ku",
    # 8192: Lexware bucht „Einnahmen als Kleinunternehmer" seit 2026 auf 8192 (vorher 8195) — kein §4 Nr. 11.
    # Bis 24.11.2026 stand hier einnahme_steuerfrei; dadurch kamen KU-Rechnungen 2026 als Courtage in Tab.
    "8510": "einnahme_steuerfrei", "8192": "einnahme_ku",
    "8924": "kfz_privatnutzung",
    # bewusst nicht
    "4830": None, "4855": None, "4320": None, "320": None, "420": None, "490": None, "2400": None, "3700": None,
    "380": None,
}
EINNAHMEN = {"einnahme_ku", "einnahme_steuerfrei", "kfz_privatnutzung"}
# Abweichende Kontierung ab einem Jahr: Konto → (ab_jahr, Kategorie, Zusatz zum Buchungstext). Gesetzt vom Aufrufer,
# z. B. Leasingraten, die Lexware auf das Anlagenkonto 0320 gebucht hat, ab 2025 als Kfz-Kosten.
UMKONTIEREN: dict[str, tuple[int, str, str]] = {}


def kategorie(konto: str, jahr: int) -> str | None:
    u = UMKONTIEREN.get(konto)
    if u and jahr >= u[0]:
        return u[1]
    return KONTEN[konto]
LOHN_VERB = {"1740", "1741", "1742", "1755"}
# Minderung einer Einnahme → Ausgabe; Erstattung einer Ausgabe → Einnahme (Tab kennt keine negativen Beträge)
GEGENKATEGORIE_AUSGABE = "fremdleistungen"
GEGENKATEGORIE_EINNAHME = {"einnahme_steuerfrei": "fremdleistungen"}


def _bank(k: int) -> bool:
    return 1200 <= k <= 1299


def _geld(k: int) -> bool:
    return _bank(k) or k in (1360, 1371, 1800, 1890, 1880)


def _person(k: int) -> bool:
    return k >= 10000


def _ergebnis(k: str) -> bool:
    return k in KONTEN


def _einnahme(konto: str) -> bool:
    return KONTEN.get(konto) in EINNAHMEN or KONTEN.get(konto) == "einnahme_ku"


@dataclasses.dataclass
class Zeile:
    jahr: int
    nr: int
    betrag: int        # Cent, positiv
    soll: str
    haben: str
    datum: str         # ISO
    beleg: str
    text: str
    guid: str | None
    schluessel: str = ""   # stabil über Exporte hinweg (für den Nachimport, Tabelle fremd_import)

    @property
    def ref(self) -> int:
        return self.jahr * 100000 + self.nr


@dataclasses.dataclass
class Buchung:
    datum: str
    text: str
    beleg: str
    geldkonto: str
    positionen: dict[str, int]   # Kategorie → Cent mit Vorzeichen
    guids: list[str]
    quelle: str                  # "zahlung" | "direkt" | "lohn"
    zeilen: list[int]
    person: str | None = None    # Personenkonto (nur Zahlungen)

    def zahlbetrag(self) -> int:
        """Geldfluss aus Sicht des Kontos: Einnahmen +, Ausgaben −."""
        return sum(v if k in EINNAHMEN else -v for k, v in self.positionen.items())


def _cent(s: str) -> int:
    return int(round(float(s.replace(".", "").replace(",", ".")) * 100))


def lesen(data: bytes, jahr: int) -> list[Zeile]:
    text = data.decode("cp1252")
    rows = list(csv.reader(io.StringIO(text), delimiter=";"))
    if not rows or rows[0][0] != "EXTF" or rows[0][3] != "Buchungsstapel":
        raise ValueError("Kein DATEV-Buchungsstapel (EXTF).")
    out = []
    gesehen: dict[str, int] = {}
    for i, r in enumerate(rows[2:]):
        if not r or not r[0]:
            continue
        basis = hashlib.sha1("|".join([str(jahr), r[0], r[1], r[6], r[7], r[9], r[10], r[13], r[19]]).encode("utf-8")).hexdigest()
        n = gesehen.get(basis, 0)
        gesehen[basis] = n + 1
        konto, gegen = r[6].lstrip("0") or "0", r[7].lstrip("0") or "0"
        soll, haben = (konto, gegen) if r[1] == "S" else (gegen, konto)
        tt, mm = r[9][:2], r[9][2:4]
        guid = None
        if r[19].startswith("BEDI"):
            guid = r[19].split('"')[1] if '"' in r[19] else r[19][5:].strip()
        out.append(Zeile(jahr, i, _cent(r[0]), soll, haben, f"{jahr}-{mm}-{tt}", r[10].strip(), r[13].strip(), guid,
                         f"{basis}:{n}"))
    return out


def _sauber(text: str) -> str:
    return re.sub(r"^(Zahlungsausg\.|Zahlungseing\.):\s*", "", text or "").strip()


def plan(zeilen: list[Zeile]) -> tuple[list[Buchung], dict]:
    """Aus allen Zeilen (alle Jahre) die Tab-Buchungen errechnen. Liefert (buchungen, bericht)."""
    rechnungen: dict[tuple, list[tuple[str, int, Zeile]]] = collections.defaultdict(list)
    zahlungen: list[tuple[tuple, Zeile, str]] = []
    direkt: dict[tuple, list[tuple[str, int, Zeile, str, str]]] = collections.defaultdict(list)
    bericht: dict[str, list] = collections.defaultdict(list)

    for z in zeilen:
        s, h = z.soll, z.haben
        si, hi = int(s), int(h)
        if _ergebnis(s) and _person(hi):          # Aufwand an Kreditor (+) / Erlösminderung an Debitor (−)
            rechnungen[(h, z.beleg)].append((s, -z.betrag if _einnahme(s) else z.betrag, z))
        elif _person(si) and _ergebnis(h):        # Debitor an Erlös (+) / Kreditor an Aufwand = Gutschrift (−)
            rechnungen[(s, z.beleg)].append((h, z.betrag if _einnahme(h) else -z.betrag, z))
        elif _person(si) and _geld(hi):           # Zahlung an Lieferant / Rückzahlung an Kunde
            zahlungen.append(((s, z.beleg), z, h))
        elif _geld(si) and _person(hi):           # Zahlungseingang Kunde / Erstattung vom Lieferanten
            zahlungen.append(((h, z.beleg), z, s))
        elif _ergebnis(s) and _geld(hi):          # Aufwand direkt bezahlt (+) / Erlösminderung ausgezahlt (−)
            direkt[(z.guid or f"{z.ref}", z.datum, h, "direkt")].append((s, -z.betrag if _einnahme(s) else z.betrag, z, h, "direkt"))
        elif _geld(si) and _ergebnis(h):          # Einnahme direkt (+) / Erstattung einer Ausgabe (−)
            direkt[(z.guid or f"{z.ref}", z.datum, s, "direkt")].append((h, z.betrag if _einnahme(h) else -z.betrag, z, s, "direkt"))
        elif _ergebnis(s) and h in LOHN_VERB:     # Lohnaufwand
            direkt[(z.beleg, z.datum, "lohn", "lohn")].append((s, z.betrag, z, h, "lohn"))
        elif s in LOHN_VERB and _ergebnis(h):     # Lohn-Erstattung/Minderung
            direkt[(z.beleg, z.datum, "lohn", "lohn")].append((h, -z.betrag, z, s, "lohn"))
        else:
            bericht["nicht_eur"].append(z)

    roh: list[Buchung] = []
    # Direkte Buchungen (je Beleg + Tag + Geldkonto eine)
    for (_, datum, geld, quelle), teile in direkt.items():
        pos: dict[str, int] = collections.defaultdict(int)
        for konto, b, z, _, _ in teile:
            kat = kategorie(konto, int(datum[:4]))
            if kat is None:
                bericht["direkt_nicht_eur"].append(z)
                continue
            pos[kat] += b
        if pos:
            z0 = teile[0][2]
            text = "Lohn (Lexware-Lohnverbuchung)" if quelle == "lohn" else _sauber(z0.text)
            zusatz = next((UMKONTIEREN[t[0]][2] for t in teile if t[0] in UMKONTIEREN
                           and int(datum[:4]) >= UMKONTIEREN[t[0]][0]), None)
            if zusatz:
                text = f"{text} {zusatz}"
            roh.append(Buchung(datum, text, z0.beleg, teile[0][3], dict(pos),
                               sorted({t[2].guid for t in teile if t[2].guid}), quelle, [t[2].ref for t in teile]))

    # Zahlungen auf Rechnungen verteilen; alle Zahlungen an/von derselben Person am selben Tag über dasselbe Geldkonto
    # werden eine Buchung (eine Sammelzahlung ist auf dem Konto ein Umsatz)
    zgruppen: dict[tuple, list[tuple[tuple, Zeile]]] = collections.defaultdict(list)
    for gruppe, z, geld in zahlungen:
        zgruppen[(gruppe, z.datum, geld)].append((gruppe, z))
    for ((person, _beleg), datum, geld), teile in zgruppen.items():
        kunde = 10000 <= int(person) < 70000
        pos: dict[str, int] = collections.defaultdict(int)
        guids: set[str] = set()
        texte: list[str] = []
        belege: list[str] = []
        refs: list[int] = []
        je_beleg: dict[tuple, list[Zeile]] = collections.defaultdict(list)
        for gruppe, z in teile:
            je_beleg[gruppe].append(z)
        for gruppe, zs in je_beleg.items():
            r = rechnungen.get(gruppe)
            if not r:
                bericht["zahlung_ohne_rechnung"].extend(zs)
                continue
            netto: dict[str, int] = collections.defaultdict(int)
            for konto, b, _ in r:
                netto[konto] += b
            netto = {k: v for k, v in netto.items() if v}
            summe = sum(netto.values())
            if not summe:
                bericht["rechnung_null"].extend(zs)
                continue
            zahl = 0
            for z in zs:
                raus = z.soll == person
                zahl += z.betrag if ((not raus) if kunde else raus) else -z.betrag
            verteilt, keys = 0, list(netto)
            for i, k in enumerate(keys):
                anteil = zahl - verteilt if i == len(keys) - 1 else round(zahl * netto[k] / summe)
                verteilt += anteil
                kat = kategorie(k, int(datum[:4]))
                if kat is None:
                    bericht["zahlung_auf_nicht_eur"].append((zs[0], k, anteil))
                    continue
                pos[kat] += anteil
            guids |= {x.guid for _, _, x in r if x.guid}
            t = next((_sauber(x.text) for _, _, x in r if x.text), _sauber(zs[0].text))
            if t and t not in texte:
                texte.append(t)
            belege.append(gruppe[1])
            refs += [z.ref for z in zs]
        if pos:
            text = texte[0] if len(texte) == 1 else f"{texte[0]} u. a. ({len(belege)} Belege)" if texte else ""
            roh.append(Buchung(datum, text, ", ".join(b for b in belege if b)[:60], geld, dict(pos), sorted(guids),
                               "zahlung", refs, person))

    # Negative Positionen umdrehen (Tab kennt keine negativen Beträge)
    buchungen = []
    for b in roh:
        pos: dict[str, int] = collections.defaultdict(int)
        for kat, v in b.positionen.items():
            if v > 0:
                pos[kat] += v
            elif v < 0:
                neu = GEGENKATEGORIE_EINNAHME.get(kat, GEGENKATEGORIE_AUSGABE) if kat in EINNAHMEN else "einnahme_ku"
                pos[neu] += -v
                bericht["umgedreht"].append((b.datum, kat, neu, -v, b.text))
        pos = {k: v for k, v in pos.items() if v}
        if pos:
            b.positionen = pos
            buchungen.append(b)
    buchungen.sort(key=lambda b: (b.datum, b.zeilen[0]))
    return buchungen, bericht


def sammelzahlungen(buchungen: list[Buchung], konto_iban: dict[str, str], umsaetze: list) -> int:
    """Mehrere Zahlungen an/von derselben Person am selben Tag über dasselbe Konto zusammenführen, wenn auf dem Konto
    genau ein Umsatz mit ihrer Summe steht und keine einzelne Zahlung allein passt (Sammelzahlung, z. B. eine
    Provisionsabrechnung über mehrere Posten). Ändert `buchungen` an Ort und Stelle, gibt die Zahl der Zusammenführungen."""
    betraege = collections.Counter((u.iban, u.datum, u.betrag_cent) for u in umsaetze)
    gruppen: dict[tuple, list[Buchung]] = collections.defaultdict(list)
    for b in buchungen:
        if b.quelle == "zahlung" and b.person and b.geldkonto in konto_iban:
            gruppen[(b.person, b.datum, b.geldkonto)].append(b)
    n = 0
    for (person, datum, geld), bs in gruppen.items():
        if len(bs) < 2:
            continue
        iban = konto_iban[geld]
        if any(betraege[(iban, datum, b.zahlbetrag())] for b in bs):
            continue
        summe = sum(b.zahlbetrag() for b in bs)
        if betraege[(iban, datum, summe)] != 1:
            continue
        haupt = bs[0]
        for b in bs[1:]:
            for k, v in b.positionen.items():
                haupt.positionen[k] = haupt.positionen.get(k, 0) + v
            haupt.guids = sorted(set(haupt.guids) | set(b.guids))
            haupt.zeilen += b.zeilen
            haupt.beleg = f"{haupt.beleg}, {b.beleg}"[:60]
            buchungen.remove(b)
        haupt.text = f"{haupt.text} u. a. ({len(bs)} Posten)"
        n += 1
    return n


# ── Schreiben ────────────────────────────────────────────────────────────────

BELEG_DETAILS = "Aus Lexware übernommen — Anlass und Teilnehmer siehe Beleg"


def ausfuehren(conn: sqlite3.Connection, *, gewerbe_id: int, buchungen: list[Buchung],
               dateien: dict[str, str]) -> dict:
    """Buchungen + Belege anlegen (ohne Commit). `dateien`: GUID → Pfad der Belegdatei."""
    kat = {r["key"]: (r["id"], r["belegpflicht_extra"]) for r in conn.execute("SELECT id, key, belegpflicht_extra FROM kategorie")}
    vergeben: dict[str, str] = {}   # GUID → Datum der Buchung, an der der Beleg hängt
    erg = {"buchungen": 0, "positionen": 0, "belege": 0, "bytes": 0, "ref": {}, "guids": {}}
    os.makedirs(settings.UPLOAD_ROOT, exist_ok=True)
    for b in buchungen:
        verweise = [vergeben[g] for g in b.guids if g in vergeben]
        text = b.text[:200]
        if verweise:
            text = f"{text} (Beleg bei der Buchung vom {verweise[0]})"[:250]
        cur = conn.execute("INSERT INTO buchung (gewerbe_id, datum, beschreibung) VALUES (?, ?, ?)",
                           (gewerbe_id, b.datum, text))
        bid = cur.lastrowid
        erg["ref"][b.zeilen[0]] = bid
        for z in b.zeilen[1:]:
            erg["ref"][z] = bid
        erg["buchungen"] += 1
        for k, v in b.positionen.items():
            kid, extra = kat[k]
            conn.execute(
                "INSERT INTO buchung_position (buchung_id, kategorie_id, betrag_cent, beleg_details) VALUES (?, ?, ?, ?)",
                (bid, kid, v, BELEG_DETAILS if extra else None),
            )
            erg["positionen"] += 1
        for g in b.guids:
            if g in vergeben or g not in dateien:
                continue
            data = open(dateien[g], "rb").read()
            stored = f"{uuid.uuid4().hex}.pdf"
            with open(os.path.join(settings.UPLOAD_ROOT, stored), "wb") as fh:
                fh.write(data)
            name = re.sub(r"[^\w.\- ]+", "", f"Lexware {b.datum} {b.beleg or g[:8]}").strip() + ".pdf"
            conn.execute(
                "INSERT INTO beleg (gewerbe_id, buchung_id, original_name, stored_name, content_type, size_bytes) "
                "VALUES (?, ?, ?, ?, 'application/pdf', ?)",
                (gewerbe_id, bid, name[:150], stored, len(data)),
            )
            vergeben[g] = b.datum
            erg["guids"][g] = bid
            erg["belege"] += 1
            erg["bytes"] += len(data)
    return erg


def schon_in_tab(conn: sqlite3.Connection, gewerbe_id: int, buchungen: list[Buchung],
                 tage: int = 7) -> tuple[list[Buchung], list[tuple[Buchung, int]]]:
    """Nachimport: Lexware-Buchungen erkennen, die es in Tab schon als eigene Buchung gibt (in der Übergangszeit direkt
    in Tab gebucht, z. B. beim Abarbeiten der Bankumsätze). Treffer = Tab-Buchung, die nicht aus einem Import stammt
    (kein fremd_import-Eintrag), mit gleichem Zahlbetrag (Einnahmen +, Ausgaben −) und Datum höchstens `tage` Tage
    entfernt; jede Tab-Buchung fängt höchstens eine Lexware-Buchung. Liefert (neu, [(lexware_buchung, tab_buchung_id)])."""
    eigene: dict[int, tuple[str, int]] = {}
    for r in conn.execute(
        "SELECT b.id, b.datum, SUM(CASE WHEN k.typ = 'einnahme' THEN p.betrag_cent ELSE -p.betrag_cent END) AS netto "
        "FROM buchung b JOIN buchung_position p ON p.buchung_id = b.id JOIN kategorie k ON k.id = p.kategorie_id "
        "WHERE b.gewerbe_id = ? AND NOT EXISTS (SELECT 1 FROM fremd_import f WHERE f.buchung_id = b.id) GROUP BY b.id",
        (gewerbe_id,),
    ):
        eigene[r["id"]] = (r["datum"], r["netto"])
    neu, doppelt = [], []
    belegt: set[int] = set()
    for b in buchungen:
        z = b.zahlbetrag()
        tag = dt.date.fromisoformat(b.datum)
        treffer = sorted(
            (abs((dt.date.fromisoformat(d) - tag).days), bid)
            for bid, (d, netto) in eigene.items()
            if bid not in belegt and netto == z and abs((dt.date.fromisoformat(d) - tag).days) <= tage
        )
        if treffer:
            belegt.add(treffer[0][1])
            doppelt.append((b, treffer[0][1]))
        else:
            neu.append(b)
    return neu, doppelt


def anlagen_uebernehmen(conn: sqlite3.Connection, *, gewerbe_id: int, anlagen: list[dict], stichtag: str) -> int:
    """Anlagen mit ihrem Buchwert zum Stichtag übernehmen (Tab rechnet die AfA ab dem Anschaffungsdatum; die Geschichte
    vor dem Stichtag steckt in den abgeschlossenen Jahren). `anlagen`: [{bezeichnung, buchwert_cent, nd_rest,
    angeschafft, ak_cent, nd}] — Datum = Stichtag, Kosten = Buchwert, Nutzungsdauer = Restnutzungsdauer."""
    kat = conn.execute("SELECT id FROM kategorie WHERE key = 'afa_beweglich'").fetchone()["id"]
    n = 0
    for a in anlagen:
        if a["buchwert_cent"] <= 100:   # Erinnerungswert 1 € — keine AfA mehr
            continue
        beschr = (f"Aus Lexware übernommen: angeschafft {a['angeschafft']}, AK {a['ak_cent'] / 100:.2f} EUR, "
                  f"Nutzungsdauer {a['nd']} J.; hier Buchwert zum {stichtag} über die Restnutzungsdauer").replace(".", ",", 1)
        conn.execute(
            "INSERT INTO afa_buchung (gewerbe_id, kategorie_id, bezeichnung, anschaffungskosten_cent, anschaffungsdatum, "
            "nutzungsdauer_jahre, afa_methode, beschreibung) VALUES (?, ?, ?, ?, ?, ?, 'linear', ?)",
            (gewerbe_id, kat, f"{a['bezeichnung']} (Buchwert {stichtag[8:10]}.{stichtag[5:7]}.{stichtag[:4]})",
             a["buchwert_cent"], stichtag, a["nd_rest"], beschr),
        )
        n += 1
    return n


# ── Kontoumsätze (Lexware „Kontoumsätze“, DATEV-ASCII ohne Kopf) ──────────────

@dataclasses.dataclass
class Umsatz:
    iban: str
    datum: str
    wert_datum: str | None
    betrag_cent: int
    gegenpartei: str
    gegen_iban: str
    zweck: str


def _iso(d: str) -> str | None:
    try:
        return dt.datetime.strptime(d.strip(), "%d.%m.%Y").date().isoformat()
    except ValueError:
        return None


def umsaetze_lesen(data: bytes) -> list[Umsatz]:
    rows = csv.reader(io.StringIO(data.decode("cp1252")), delimiter=";")
    out = []
    for r in rows:
        if len(r) < 17 or not r[1] or not _iso(r[4]):
            continue
        zweck = " ".join(x.strip() for x in r[11:16] if x and x.strip())
        out.append(Umsatz(r[1].replace(" ", ""), _iso(r[4]), _iso(r[5]), _cent(r[6]), r[7].strip(),
                          r[10].replace(" ", ""), zweck))
    return out


GRUENDE = [
    (lambda k: k in ("1800", "1810", "1820", "1840", "1880", "1890"), "Privat"),
    (lambda k: k == "1360" or _bank(int(k)), "Umbuchung zwischen eigenen Konten"),
    (lambda k: k in LOHN_VERB, "Lohn und Sozialabgaben (über die Lohnverbuchung gebucht)"),
    (lambda k: k == "4320", "Gewerbesteuer (keine Betriebsausgabe)"),
    (lambda k: k == "320", "Pkw-Leasing (bei Lexware als Anlage gebucht)"),
    (lambda k: k in ("420", "490", "480"), "Anlage (Abschreibung unter Anlagen)"),
]


def bank_zeilen(zeilen: list[Zeile], konto_iban: dict[str, str], ref_buchung: dict[int, int] | None = None) -> list[dict]:
    """Jede Lexware-Zeile, die ein Bankkonto berührt: Konto, Datum, Betrag (+ Eingang), Gegenkonto. Zeilen, die zur
    selben Tab-Buchung gehören, werden je Konto und Tag zu einer zusammengefasst (ein Umsatz auf dem Konto)."""
    ref_buchung = ref_buchung or {}
    einzeln, gruppen = [], {}
    for z in zeilen:
        for bank, gegen, vz in ((z.soll, z.haben, +1), (z.haben, z.soll, -1)):
            if not (_bank(int(bank)) and bank in konto_iban):
                continue
            eintrag = {"iban": konto_iban[bank], "datum": z.datum, "betrag": vz * z.betrag, "gegen": gegen,
                       "ref": z.ref, "text": z.text}
            bid = ref_buchung.get(z.ref)
            if bid is None:
                einzeln.append(eintrag)
                continue
            key = (eintrag["iban"], z.datum, bid)
            if key in gruppen:
                gruppen[key]["betrag"] += eintrag["betrag"]
            else:
                gruppen[key] = eintrag
    return einzeln + list(gruppen.values())


def bank_importieren(conn: sqlite3.Connection, *, gewerbe_id: int, umsaetze: list[Umsatz], bzeilen: list[dict],
                     ref_buchung: dict[int, int], kontonamen: dict[str, str], rechnungsgruppe: dict[int, str],
                     offen_ab: str, email: str) -> dict:
    """Kontoumsätze anlegen (Dubletten gegen Vorhandenes: Tag + Betrag), mit den importierten Buchungen verknüpfen und
    Nicht-EÜR-Umsätze mit Grund ignorieren. Was bis `offen_ab` nicht zuzuordnen ist, wird als Altbestand ignoriert."""
    from .bank_import import konto_aufloesen

    erg = collections.Counter()
    konten: dict[str, sqlite3.Row] = {}
    neu_ids: list[tuple[int, Umsatz]] = []
    gesehen: dict[str, int] = {}
    belegt: set[int] = set()
    for u in umsaetze:
        if u.iban not in konten:
            konten[u.iban] = konto_aufloesen(conn, gewerbe_id, None, u.iban, kontonamen.get(u.iban))
        k = konten[u.iban]
        basis = hashlib.sha256(f"{u.datum}|{u.betrag_cent}|{u.gegenpartei.lower()}|{u.zweck}".encode()).hexdigest()
        n = gesehen.get(basis, 0)
        gesehen[basis] = n + 1
        fp = f"lx:{basis}:{n}"
        if conn.execute("SELECT 1 FROM bank_umsatz WHERE konto_id = ? AND fingerprint = ?", (k["id"], fp)).fetchone():
            erg["schon_da"] += 1
            continue
        vorhanden = next((r["id"] for r in conn.execute(
            "SELECT id FROM bank_umsatz WHERE konto_id = ? AND datum = ? AND betrag_cent = ? AND fingerprint NOT LIKE 'lx:%' "
            "ORDER BY id", (k["id"], u.datum, u.betrag_cent)) if r["id"] not in belegt), None)
        if vorhanden:
            belegt.add(vorhanden)
            neu_ids.append((vorhanden, u))   # schon vorhanden (Datei/Abruf): nur zuordnen
            erg["dublette"] += 1
            continue
        uid = conn.execute(
            "INSERT INTO bank_umsatz (konto_id, gewerbe_id, datum, wert_datum, betrag_cent, gegenpartei, gegenpartei_iban, "
            "verwendungszweck, fingerprint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (k["id"], gewerbe_id, u.datum, u.wert_datum, u.betrag_cent, u.gegenpartei or None, u.gegen_iban or None,
             u.zweck or None, fp),
        ).lastrowid
        neu_ids.append((uid, u))
        erg["neu"] += 1

    # Zuordnen: je Umsatz die Lexware-Zeile mit gleichem Konto, Tag und Betrag (sonst ± 3 Tage)
    frei = collections.defaultdict(list)
    for bz in bzeilen:
        frei[(bz["iban"], bz["betrag"])].append(bz)
    for uid, u in neu_ids:
        kandidaten = frei.get((u.iban, u.betrag_cent), [])
        treffer = next((c for c in kandidaten if c["datum"] == u.datum), None)
        if treffer is None:
            nah = [c for c in kandidaten
                   if abs((dt.date.fromisoformat(c["datum"]) - dt.date.fromisoformat(u.datum)).days) <= 3]
            treffer = nah[0] if len(nah) == 1 else None
        row = conn.execute("SELECT buchung_id, status FROM bank_umsatz WHERE id = ?", (uid,)).fetchone()
        if row["buchung_id"] or row["status"] != "offen":
            erg["schon_zugeordnet"] += 1
            if treffer:
                kandidaten.remove(treffer)
            continue
        if treffer:
            kandidaten.remove(treffer)
            bid = ref_buchung.get(treffer["ref"])
            if bid and not conn.execute("SELECT 1 FROM bank_umsatz WHERE buchung_id = ?", (bid,)).fetchone():
                conn.execute("UPDATE bank_umsatz SET buchung_id = ?, zugeordnet_am = datetime('now') WHERE id = ?", (bid, uid))
                erg["verknuepft"] += 1
                continue
            if bid:
                erg["buchung_schon_verknuepft"] += 1
                continue
            gegen = rechnungsgruppe.get(treffer["ref"], treffer["gegen"])
            grund = next((g for f, g in GRUENDE if f(gegen)), None)
            if grund:
                conn.execute("UPDATE bank_umsatz SET status = 'ignoriert', ignoriert_grund = ? WHERE id = ?", (grund, uid))
                erg["ignoriert"] += 1
                continue
        if u.datum < offen_ab:
            conn.execute("UPDATE bank_umsatz SET status = 'ignoriert', ignoriert_grund = ? WHERE id = ?",
                         ("Altbestand aus Lexware (dort bearbeitet)", uid))
            erg["altbestand"] += 1
        else:
            erg["offen"] += 1
    return dict(erg)


def rechnungsgegenkonten(zeilen: list[Zeile]) -> dict[int, str]:
    """Für Zahlungszeilen über Personenkonten: das Konto der Rechnung (z. B. 1742 Sozialabgaben, 1840 Spenden) — damit
    nicht übernommene Zahlungen den richtigen Grund bekommen."""
    rech: dict[tuple, str] = {}
    for z in zeilen:
        if _person(int(z.haben)) and not _geld(int(z.soll)):
            rech.setdefault((z.haben, z.beleg), z.soll)
        elif _person(int(z.soll)) and not _geld(int(z.haben)):
            rech.setdefault((z.soll, z.beleg), z.haben)
    out = {}
    for z in zeilen:
        for p, g in ((z.soll, z.haben), (z.haben, z.soll)):
            if _person(int(p)) and _geld(int(g)) and (p, z.beleg) in rech:
                out[z.ref] = rech[(p, z.beleg)]
    return out
