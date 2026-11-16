"""Bilanz und GuV als Entwurf für die Steuerberatung (BILANZ.md).

Tab führt kein zweites Hauptbuch. Für ein Bilanz-Jahr baut `journal()` aus den vorhandenen Daten ein doppeltes Journal
(jede Zeile: Soll-Konto, Haben-Konto, Betrag) und `auswertung()` summiert es zu GuV, Bilanz und Abstimmung. Was Tab nicht
zuordnen kann, landet auf dem Verrechnungskonto — so geht die Bilanz immer auf, und die Abstimmung sagt, woran es liegt.

Konten (intern): Bestand `anlage`, `bank:<id>`, `kasse`, `forderungen`, `forderungen_sonst`, `ara`, `finanzamt`,
`verrechnung`, `eigenkapital`, `privat`, `rueckstellungen`, `verbindlichkeiten`, `verb_sonst`, `pra`; Erfolg `guv:<posten>`.
Saldo = Soll − Haben (Aktiv- und Aufwandskonten positiv).
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import sqlite3

from . import besteuerung as best
from . import gewinnermittlung as gw
from . import rechnung_summen
from .afa import afa_jahr, verlauf
from .privatanteil import betrieblich_netto_cent, betrieblich_ust_cent, privat_cent

# ── Gliederung ───────────────────────────────────────────────────────────────

GUV_POSTEN = [  # (key, Nr., Bezeichnung, Ertrag?)
    ("umsatzerloese", "1.", "Umsatzerlöse", True),
    ("sonstige_ertraege", "4.", "Sonstige betriebliche Erträge", True),
    ("material_waren", "5a.", "Aufwendungen für Waren und Material", False),
    ("material_leistungen", "5b.", "Aufwendungen für bezogene Leistungen", False),
    ("personal", "6.", "Personalaufwand", False),
    ("abschreibungen", "7.", "Abschreibungen", False),
    ("sonstige_aufwendungen", "8.", "Sonstige betriebliche Aufwendungen", False),
    ("zinsen", "13.", "Zinsen und ähnliche Aufwendungen", False),
    ("steuern_ertrag", "14.", "Steuern vom Einkommen und vom Ertrag", False),
]
GUV_KEYS = {p[0] for p in GUV_POSTEN}

KATEGORIE_GUV = {
    "einnahme_ku": "umsatzerloese", "einnahme_ust": "umsatzerloese", "einnahme_steuerfrei": "umsatzerloese",
    "veraeusserung_av": "sonstige_ertraege", "kfz_privatnutzung": "sonstige_ertraege",
    "entnahme_sonstig": "sonstige_ertraege",
    "waren": "material_waren", "fremdleistungen": "material_leistungen", "personal": "personal",
    "gwg": "abschreibungen", "zinsen": "zinsen",
}
PAUSCHALEN = {"fahrtkosten_kfz", "wege_wohnung_betrieb", "homeoffice_pauschale", "verpflegungsmehraufwand"}
ENTNAHMEN = {"kfz_privatnutzung", "entnahme_sonstig"}

# Bilanzposten: (key, Seite, Bezeichnung, Konten-Präfixe). Saldo mit falschem Vorzeichen wandert auf GEGENPOSTEN.
AKTIVA = [
    ("anlage", "A. Anlagevermögen – Sachanlagen"),
    ("forderungen", "B. II. 1. Forderungen aus Lieferungen und Leistungen"),
    ("forderungen_sonst", "B. II. 2. Sonstige Vermögensgegenstände"),
    ("bank", "B. IV. Kassenbestand, Guthaben bei Kreditinstituten"),
    ("ara", "C. Rechnungsabgrenzungsposten"),
]
PASSIVA = [
    ("eigenkapital", "A. Eigenkapital"),
    ("rueckstellungen", "B. Rückstellungen"),
    ("verbindlichkeiten", "C. 1. Verbindlichkeiten aus Lieferungen und Leistungen"),
    ("verb_sonst", "C. 2. Sonstige Verbindlichkeiten"),
    ("pra", "D. Rechnungsabgrenzungsposten"),
]
# Konto → Bilanzposten bei Soll-Saldo (aktiv) / Haben-Saldo (passiv)
KONTO_POSTEN = {
    "anlage": ("anlage", "verb_sonst"),
    "kasse": ("bank", "verb_sonst"),
    "forderungen": ("forderungen", "verb_sonst"),
    "forderungen_sonst": ("forderungen_sonst", "verb_sonst"),
    "ara": ("ara", "pra"),
    "finanzamt": ("forderungen_sonst", "verb_sonst"),
    "verrechnung": ("forderungen_sonst", "verb_sonst"),
    "rueckstellungen": ("forderungen_sonst", "rueckstellungen"),
    "verbindlichkeiten": ("forderungen_sonst", "verbindlichkeiten"),
    "verb_sonst": ("forderungen_sonst", "verb_sonst"),
    "pra": ("ara", "pra"),
}
BESTAND = set(KONTO_POSTEN) | {"eigenkapital", "privat"}
KONTO_NAMEN = {
    "anlage": "Anlagevermögen", "kasse": "Kasse", "forderungen": "Forderungen aus Lieferungen und Leistungen",
    "forderungen_sonst": "Sonstige Forderungen", "ara": "Aktive Rechnungsabgrenzung", "finanzamt": "Finanzamt (USt/Vorsteuer)",
    "verrechnung": "Verrechnungskonto", "eigenkapital": "Eigenkapital", "privat": "Privat (Einlagen/Entnahmen)",
    "rueckstellungen": "Rückstellungen", "verbindlichkeiten": "Verbindlichkeiten aus Lieferungen und Leistungen",
    "verb_sonst": "Sonstige Verbindlichkeiten", "pra": "Passive Rechnungsabgrenzung",
}
# In Eröffnung und Abschlussbuchungen frei wählbar (Bank kommt dazu)
EROEFFNUNG_AKTIV = ["anlage", "kasse", "forderungen", "forderungen_sonst", "ara"]
EROEFFNUNG_PASSIV = ["rueckstellungen", "verbindlichkeiten", "verb_sonst", "pra"]
ABSCHLUSS_KONTEN = ["kasse", "forderungen", "forderungen_sonst", "ara", "finanzamt", "verrechnung", "privat",
                    "rueckstellungen", "verbindlichkeiten", "verb_sonst", "pra", "anlage"]


def konto_name(conn: sqlite3.Connection, konto: str) -> str:
    if konto.startswith("guv:"):
        return next((p[2] for p in GUV_POSTEN if p[0] == konto[4:]), konto)
    if konto.startswith("bank:"):
        r = conn.execute("SELECT name FROM bankkonto WHERE id = ?", (int(konto[5:]),)).fetchone()
        return f"Bank {r['name']}" if r else konto
    return KONTO_NAMEN.get(konto, konto)


def konto_gueltig(conn: sqlite3.Connection, gewerbe_id: int, konto: str) -> bool:
    if konto in ABSCHLUSS_KONTEN:
        return True
    if konto.startswith("guv:"):
        return konto[4:] in GUV_KEYS
    if konto.startswith("bank:") and konto[5:].isdigit():
        return conn.execute("SELECT 1 FROM bankkonto WHERE id = ? AND gewerbe_id = ?",
                            (int(konto[5:]), gewerbe_id)).fetchone() is not None
    return False


# ── Journal ──────────────────────────────────────────────────────────────────

class _J:
    def __init__(self):
        self.zeilen: list[dict] = []

    def add(self, datum: str, soll: str, haben: str, betrag: int, text: str, quelle: str, ref: str | None = None,
            kat: str | None = None):
        """`kat`: Herkunft für den DATEV-Export (Kategorie-Key oder ust/vorsteuer/skonto/ausfall/afa/gewst/rechnung)."""
        if betrag == 0 or soll == haben:
            return
        if betrag < 0:
            soll, haben, betrag = haben, soll, -betrag
        self.zeilen.append({"datum": datum, "soll": soll, "haben": haben, "betrag_cent": betrag, "text": text,
                            "quelle": quelle, "ref": ref, "kat": kat})


def _guv_konto(key: str, ist_afa: bool) -> str:
    if ist_afa:
        return "guv:abschreibungen"
    return "guv:" + KATEGORIE_GUV.get(key, "sonstige_aufwendungen")


def _umsatz_gegenkonto(grund: str | None) -> str:
    g = (grund or "").lower()
    if "gewerbesteuer" in g:
        return "guv:steuern_ertrag"
    if "privat" in g or "nicht betrieblich" in g or "einkommensteuer" in g:
        return "privat"
    return "verrechnung"


def journal(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> list[dict]:
    """Journal der laufenden Geschäftsvorfälle eines Jahres (ohne Eröffnung und ohne Jahresabschluss ins Eigenkapital)."""
    von, bis = f"{jahr}-01-01", f"{jahr}-12-31"
    j = _J()
    regel = best.ist_regel(conn, gewerbe_id, jahr)

    # Buchungen, die eine Zahlung auf eine Tab-Rechnung sind: Ertrag kommt von der Rechnung, die Zahlung tilgt nur.
    rz_buchung = {
        r["buchung_id"] for r in conn.execute(
            "SELECT z.buchung_id FROM rechnung_zahlung z WHERE z.gewerbe_id = ? AND z.buchung_id IS NOT NULL "
            "UNION SELECT buchung_id FROM rechnung WHERE gewerbe_id = ? AND buchung_id IS NOT NULL",
            (gewerbe_id, gewerbe_id))
    }

    buchungen = conn.execute(
        "SELECT id, datum, rechnungsdatum, offen, beschreibung FROM buchung WHERE gewerbe_id = ? AND "
        "((COALESCE(rechnungsdatum, datum) BETWEEN ? AND ?) OR (offen = 0 AND datum BETWEEN ? AND ?))",
        (gewerbe_id, von, bis, von, bis),
    ).fetchall()
    for b in buchungen:
        rdatum = b["rechnungsdatum"] or b["datum"]
        text = b["beschreibung"] or f"Buchung {b['id']}"
        ref = f"T{b['id']}"
        pos = conn.execute(
            "SELECT p.betrag_cent, p.privat_bp, p.ust_cent, k.key, k.typ, k.ist_afa FROM buchung_position p "
            "JOIN kategorie k ON k.id = p.kategorie_id WHERE p.buchung_id = ?", (b["id"],)
        ).fetchall()
        ford = verb = 0  # was über Forderungen/Verbindlichkeiten bezahlt wird
        ist_rz = b["id"] in rz_buchung
        for p in pos:
            key, betrag = p["key"], p["betrag_cent"]
            if ist_rz and p["typ"] == "einnahme":
                ford += betrag
                continue
            in_jahr = von <= rdatum <= bis
            if p["typ"] == "einnahme":
                ust = p["ust_cent"] if regel else 0
                if key == "ust_erstattung":
                    if in_jahr:
                        j.add(rdatum, "forderungen", "finanzamt", betrag, text, "buchung", ref, key)
                    ford += betrag
                    continue
                if key in ENTNAHMEN:
                    if in_jahr:
                        j.add(rdatum, "privat", _guv_konto(key, False), betrag - ust, text, "buchung", ref, key)
                        j.add(rdatum, "privat", "finanzamt", ust, text + " (USt)", "buchung", ref, "ust")
                    continue
                if in_jahr:
                    j.add(rdatum, "forderungen", _guv_konto(key, False), betrag - ust, text, "buchung", ref, key)
                    j.add(rdatum, "forderungen", "finanzamt", ust, text + " (USt)", "buchung", ref, "ust")
                ford += betrag
            else:
                if key == "ust_zahlung":
                    if in_jahr:
                        j.add(rdatum, "finanzamt", "verbindlichkeiten", betrag, text, "buchung", ref, key)
                    verb += betrag
                    continue
                gegen = "verbindlichkeiten"
                if key in PAUSCHALEN:
                    gegen = "privat"
                elif key == "restbuchwert":
                    gegen = "anlage"
                if in_jahr:
                    bp, ust = p["privat_bp"] or 0, (p["ust_cent"] if regel else 0)
                    netto = betrieblich_netto_cent(betrag, ust, bp)
                    vst = betrieblich_ust_cent(ust, bp)
                    priv = privat_cent(betrag, bp)
                    j.add(rdatum, _guv_konto(key, bool(p["ist_afa"])), gegen, netto, text, "buchung", ref, key)
                    j.add(rdatum, "finanzamt", gegen, vst, text + " (Vorsteuer)", "buchung", ref, "vorsteuer")
                    j.add(rdatum, "privat", gegen, priv, text + " (Privatanteil)", "buchung", ref, key)
                if gegen == "verbindlichkeiten":
                    verb += betrag
        # Zahlungsseite: über das Verrechnungskonto; die Bankumsätze buchen dorthin (siehe unten)
        if not b["offen"] and von <= b["datum"] <= bis:
            j.add(b["datum"], "verrechnung", "forderungen", ford, text + " (Zahlung)", "zahlung", ref)
            j.add(b["datum"], "verbindlichkeiten", "verrechnung", verb, text + " (Zahlung)", "zahlung", ref)

    # Tab-Rechnungen: Ertrag zum Rechnungsdatum
    for r in conn.execute(
        "SELECT id, nummer, datum, empfaenger_name, steuerhinweis FROM rechnung WHERE gewerbe_id = ? "
        "AND status IN ('versendet','bezahlt') AND datum BETWEEN ? AND ?", (gewerbe_id, von, bis)
    ):
        s = rechnung_summen.rechnung(conn, r["id"])
        rkat = ("einnahme_steuerfrei" if r["steuerhinweis"] == "vers4nr11" else "einnahme_ust" if regel
                else "einnahme_ku")
        text, ref = f"Rechnung {r['nummer']} {r['empfaenger_name']}", f"R{r['id']}"
        ust = s["ust_cent"] if regel else 0
        j.add(r["datum"], "forderungen", "guv:umsatzerloese", s["brutto_cent"] - ust, text, "rechnung", ref, rkat)
        j.add(r["datum"], "forderungen", "finanzamt", ust, text + " (USt)", "rechnung", ref, "ust")
    for z in conn.execute(
        "SELECT z.datum, z.betrag_cent, z.art, z.buchung_id, r.nummer, r.id AS rid FROM rechnung_zahlung z "
        "JOIN rechnung r ON r.id = z.rechnung_id WHERE z.gewerbe_id = ? AND z.datum BETWEEN ? AND ?",
        (gewerbe_id, von, bis)
    ):
        text, ref = f"Rechnung {z['nummer']}", f"R{z['rid']}"
        if z["art"] == "skonto":
            j.add(z["datum"], "guv:umsatzerloese", "forderungen", z["betrag_cent"], text + " (Skonto)", "rechnung", ref, "skonto")
        elif z["art"] == "ausfall":
            j.add(z["datum"], "guv:sonstige_aufwendungen", "forderungen", z["betrag_cent"], text + " (Forderungsausfall)",
                  "rechnung", ref, "ausfall")
        elif z["buchung_id"] is None:
            j.add(z["datum"], "verrechnung", "forderungen", z["betrag_cent"], text + " (Zahlung, nicht gebucht)",
                  "rechnung", ref)

    # Anlagen: Zugang und AfA
    for a in conn.execute("SELECT * FROM afa_buchung WHERE gewerbe_id = ?", (gewerbe_id,)):
        text, ref = a["bezeichnung"], f"A{a['id']}"
        if von <= a["anschaffungsdatum"] <= bis:
            vst = (a["vorsteuer_cent"] or 0) if regel else 0
            j.add(a["anschaffungsdatum"], "anlage", "verrechnung", a["anschaffungskosten_cent"], text + " (Zugang)",
                  "anlage", ref, "sammelposten" if a["afa_methode"] == "sammelposten" else "anlage")
            j.add(a["anschaffungsdatum"], "finanzamt", "verrechnung", vst, text + " (Vorsteuer)", "anlage", ref, "vorsteuer")
        j.add(bis, "guv:abschreibungen", "anlage", afa_jahr(a, jahr), text + " (AfA)", "afa", ref,
              "afa_sammelposten" if a["afa_methode"] == "sammelposten" else "afa")

    # Bankumsätze: jeder Umsatz gegen das Verrechnungskonto, außer erkennbar privat oder Gewerbesteuer
    for u in conn.execute(
        "SELECT u.id, u.konto_id, u.datum, u.betrag_cent, u.gegenpartei, u.status, u.ignoriert_grund, u.buchung_id "
        "FROM bank_umsatz u WHERE u.gewerbe_id = ? AND u.datum BETWEEN ? AND ?", (gewerbe_id, von, bis)
    ):
        gegen = "verrechnung"
        if u["buchung_id"] is None and u["status"] == "ignoriert":
            gegen = _umsatz_gegenkonto(u["ignoriert_grund"])
        text = u["gegenpartei"] or "Bankumsatz"
        if u["status"] == "ignoriert" and u["ignoriert_grund"]:
            text += f" ({u['ignoriert_grund']})"
        j.add(u["datum"], f"bank:{u['konto_id']}", gegen, u["betrag_cent"], text, "bank", f"U{u['id']}",
              "gewst" if gegen == "guv:steuern_ertrag" else None)

    # Abschlussbuchungen
    for a in conn.execute(
        "SELECT * FROM abschlussbuchung WHERE gewerbe_id = ? AND datum BETWEEN ? AND ? ORDER BY datum, id",
        (gewerbe_id, von, bis)
    ):
        j.add(a["datum"], a["soll"], a["haben"], a["betrag_cent"], a["text"] or "Abschlussbuchung", "abschluss",
              f"S{a['id']}")
    j.zeilen.sort(key=lambda z: (z["datum"], z["quelle"], z["ref"] or ""))
    return j.zeilen


# ── Eröffnung ────────────────────────────────────────────────────────────────

def _salden(zeilen: list[dict], start: dict[str, int] | None = None) -> dict[str, int]:
    s = dict(start or {})
    for z in zeilen:
        s[z["soll"]] = s.get(z["soll"], 0) + z["betrag_cent"]
        s[z["haben"]] = s.get(z["haben"], 0) - z["betrag_cent"]
    return s


def eroeffnung_manuell(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> dict[str, int]:
    """Eingetragene Eröffnungswerte als Salden (Aktiva +, Passiva −); Eigenkapital = Ausgleich."""
    s: dict[str, int] = {}
    for r in conn.execute("SELECT posten, betrag_cent FROM bilanz_eroeffnung WHERE gewerbe_id = ? AND jahr = ?",
                          (gewerbe_id, jahr)):
        aktiv = r["posten"] in EROEFFNUNG_AKTIV or r["posten"].startswith("bank:")
        s[r["posten"]] = s.get(r["posten"], 0) + (r["betrag_cent"] if aktiv else -r["betrag_cent"])
    s["eigenkapital"] = -sum(s.values())
    return s


def eroeffnung(conn: sqlite3.Connection, gewerbe_id: int, jahr: int, _tiefe: int = 0) -> dict[str, int]:
    """Eröffnungssalden: im ersten Bilanz-Jahr die eingetragenen Werte, danach der Schlussbestand des Vorjahres."""
    erstes = gw.erstes_bilanzjahr(conn, gewerbe_id, jahr)
    if erstes is None or erstes == jahr or _tiefe > 60:
        return eroeffnung_manuell(conn, gewerbe_id, jahr)
    return schluss(conn, gewerbe_id, jahr - 1, _tiefe + 1)


def schluss(conn: sqlite3.Connection, gewerbe_id: int, jahr: int, _tiefe: int = 0) -> dict[str, int]:
    """Schlussbestand der Bestandskonten nach Abschluss von GuV und Privat ins Eigenkapital."""
    s = _salden(journal(conn, gewerbe_id, jahr), eroeffnung(conn, gewerbe_id, jahr, _tiefe))
    ek = s.get("eigenkapital", 0)
    for k in list(s):
        if k.startswith("guv:") or k == "privat":
            ek += s.pop(k)
    s["eigenkapital"] = ek
    return {k: v for k, v in s.items() if v != 0 or k == "eigenkapital"}


def _anlagen_buchwert(conn: sqlite3.Connection, gewerbe_id: int, stichtag_jahr: int) -> list[dict]:
    """Buchwert je Anlage zum 31.12. von `stichtag_jahr`."""
    out = []
    for a in conn.execute("SELECT * FROM afa_buchung WHERE gewerbe_id = ? ORDER BY anschaffungsdatum", (gewerbe_id,)):
        if int(a["anschaffungsdatum"][:4]) > stichtag_jahr:
            continue
        if a["abgang_datum"] and a["abgang_datum"][:4] <= str(stichtag_jahr) and a["afa_methode"] != "sammelposten":
            continue  # abgegangen, Restbuchwert wurde als Buchung erfasst
        plan = verlauf(a["anschaffungskosten_cent"], a["anschaffungsdatum"], a["nutzungsdauer_jahre"], a["afa_methode"],
                       a["degressiv_bp"], a["linear_ab_jahr"], a["abgang_datum"])
        afa = sum(z["afa_cent"] for z in plan if z["jahr"] <= stichtag_jahr)
        bw = a["anschaffungskosten_cent"] - afa
        if bw > 0:
            out.append({"id": a["id"], "bezeichnung": a["bezeichnung"], "anschaffungsdatum": a["anschaffungsdatum"],
                        "anschaffungskosten_cent": a["anschaffungskosten_cent"], "buchwert_cent": bw})
    return out


def _offene_rechnungen(conn: sqlite3.Connection, gewerbe_id: int, stichtag: str) -> list[dict]:
    out = []
    for r in conn.execute(
        "SELECT id, nummer, datum, empfaenger_name FROM rechnung WHERE gewerbe_id = ? AND status IN ('versendet','bezahlt') "
        "AND datum <= ? ORDER BY datum", (gewerbe_id, stichtag)
    ):
        summe = rechnung_summen.rechnung(conn, r["id"])["brutto_cent"]
        weg = conn.execute("SELECT COALESCE(SUM(betrag_cent), 0) FROM rechnung_zahlung WHERE rechnung_id = ? AND datum <= ?",
                           (r["id"], stichtag)).fetchone()[0]
        if summe - weg > 0:
            out.append({"id": r["id"], "nummer": r["nummer"], "datum": r["datum"], "empfaenger": r["empfaenger_name"],
                        "offen_cent": summe - weg})
    return out


def eroeffnung_vorschlag(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> dict:
    """Vorschläge für das erste Bilanz-Jahr aus den Daten bis 31.12. des Vorjahres."""
    stichtag = f"{jahr - 1}-12-31"
    anlagen = _anlagen_buchwert(conn, gewerbe_id, jahr - 1)
    rechnungen = _offene_rechnungen(conn, gewerbe_id, stichtag)
    return {
        "stichtag": stichtag,
        "anlage_cent": sum(a["buchwert_cent"] for a in anlagen),
        "anlagen": anlagen,
        "forderungen_cent": sum(r["offen_cent"] for r in rechnungen),
        "rechnungen": rechnungen,
    }


def uebergangsgewinn(eroeffnung_salden: dict[str, int]) -> int:
    """R 4.6 EStR (vereinfacht): Forderungen + aktive RAP − Verbindlichkeiten − Rückstellungen − passive RAP."""
    s = eroeffnung_salden
    return (s.get("forderungen", 0) + s.get("forderungen_sonst", 0) + s.get("ara", 0)
            + s.get("verbindlichkeiten", 0) + s.get("rueckstellungen", 0) + s.get("verb_sonst", 0) + s.get("pra", 0))


# ── Auswertung ───────────────────────────────────────────────────────────────

def auswertung(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> dict:
    if not gw.ist_bilanz(conn, gewerbe_id, jahr):
        raise ValueError(f"{jahr} ist für dieses Gewerbe kein Bilanz-Jahr (Gewinnermittlung: EÜR).")
    erstes = gw.erstes_bilanzjahr(conn, gewerbe_id, jahr)
    eb = eroeffnung(conn, gewerbe_id, jahr)
    zeilen = journal(conn, gewerbe_id, jahr)
    s = _salden(zeilen, eb)

    # GuV
    guv = []
    for key, nr, name, ertrag in GUV_POSTEN:
        saldo = s.get(f"guv:{key}", 0)
        guv.append({"key": key, "nr": nr, "name": name, "ertrag": ertrag,
                    "betrag_cent": -saldo if ertrag else saldo})
    ertraege = sum(-s.get(f"guv:{p[0]}", 0) for p in GUV_POSTEN if p[3])
    aufwand = sum(s.get(f"guv:{p[0]}", 0) for p in GUV_POSTEN if not p[3])
    ergebnis = -sum(v for k, v in s.items() if k.startswith("guv:"))

    # Hinzurechnungen (steuerlicher Gewinn)
    bewirtung = _bewirtung_nicht_abziehbar(conn, gewerbe_id, jahr)
    gewst = s.get("guv:steuern_ertrag", 0)
    hinzu = [h for h in [
        {"text": "Bewirtung: nicht abziehbarer Teil (30 %)", "betrag_cent": bewirtung},
        {"text": "Gewerbesteuer (§ 4 Abs. 5b EStG)", "betrag_cent": gewst},
    ] if h["betrag_cent"]]

    # Privat / Eigenkapital
    einlagen = sum(z["betrag_cent"] for z in zeilen if z["haben"] == "privat")
    entnahmen = sum(z["betrag_cent"] for z in zeilen if z["soll"] == "privat")
    ek_anfang = -eb.get("eigenkapital", 0)
    ek_ende = ek_anfang + einlagen - entnahmen + ergebnis

    # Bilanz
    posten: dict[str, list[dict]] = {}
    for konto, saldo in sorted(s.items()):
        if konto.startswith("guv:") or konto in ("privat", "eigenkapital") or saldo == 0:
            continue
        if konto.startswith("bank:"):
            ziel = "bank" if saldo > 0 else "verb_sonst"
        else:
            akt, pas = KONTO_POSTEN[konto]
            ziel = akt if saldo > 0 else pas
        posten.setdefault(ziel, []).append({"konto": konto, "name": konto_name(conn, konto), "betrag_cent": abs(saldo)})

    def seite(gliederung):
        out = []
        for key, name in gliederung:
            if key == "eigenkapital":
                out.append({"key": key, "name": name, "betrag_cent": ek_ende, "konten": [
                    {"konto": "ek_anfang", "name": "Eigenkapital 1.1.", "betrag_cent": ek_anfang},
                    {"konto": "einlagen", "name": "Einlagen", "betrag_cent": einlagen},
                    {"konto": "entnahmen", "name": "Entnahmen", "betrag_cent": -entnahmen},
                    {"konto": "ergebnis", "name": "Jahresüberschuss" if ergebnis >= 0 else "Jahresfehlbetrag",
                     "betrag_cent": ergebnis},
                ]})
                continue
            konten = posten.get(key, [])
            out.append({"key": key, "name": name, "betrag_cent": sum(k["betrag_cent"] for k in konten), "konten": konten})
        return out

    aktiva, passiva = seite(AKTIVA), seite(PASSIVA)
    summe_a = sum(p["betrag_cent"] for p in aktiva)
    summe_p = sum(p["betrag_cent"] for p in passiva)

    return {
        "gewerbe_id": gewerbe_id, "jahr": jahr, "erstes_bilanzjahr": erstes, "regel": best.ist_regel(conn, gewerbe_id, jahr),
        "guv": guv, "ertraege_cent": ertraege, "aufwand_cent": aufwand, "ergebnis_cent": ergebnis,
        "hinzurechnungen": hinzu, "steuerlicher_gewinn_cent": ergebnis + sum(h["betrag_cent"] for h in hinzu),
        "aktiva": aktiva, "passiva": passiva, "summe_aktiva_cent": summe_a, "summe_passiva_cent": summe_p,
        "eigenkapital": {"anfang_cent": ek_anfang, "einlagen_cent": einlagen, "entnahmen_cent": entnahmen,
                         "ergebnis_cent": ergebnis, "ende_cent": ek_ende},
        "uebergangsgewinn_cent": uebergangsgewinn(eb) if erstes == jahr else None,
        "abstimmung": abstimmung(conn, gewerbe_id, jahr, s, zeilen, summe_a - summe_p),
        "anzahl_journal": len(zeilen),
    }


def _bewirtung_nicht_abziehbar(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> int:
    regel = best.ist_regel(conn, gewerbe_id, jahr)
    summe = 0
    for p in conn.execute(
        "SELECT p.betrag_cent, p.privat_bp, p.ust_cent, k.abzug_quote FROM buchung_position p "
        "JOIN buchung b ON b.id = p.buchung_id JOIN kategorie k ON k.id = p.kategorie_id "
        "WHERE b.gewerbe_id = ? AND COALESCE(b.rechnungsdatum, b.datum) BETWEEN ? AND ? AND k.abzug_quote < 1",
        (gewerbe_id, f"{jahr}-01-01", f"{jahr}-12-31")
    ):
        netto = betrieblich_netto_cent(p["betrag_cent"], p["ust_cent"] if regel else 0, p["privat_bp"] or 0)
        summe += netto - round(netto * p["abzug_quote"])
    return summe


def abstimmung(conn: sqlite3.Connection, gewerbe_id: int, jahr: int, s: dict[str, int], zeilen: list[dict],
               differenz: int) -> list[dict]:
    """Prüfpunkte: was die Bilanz unsicher macht. ton: ok | warn | neg."""
    von, bis = f"{jahr}-01-01", f"{jahr}-12-31"
    out = []
    if differenz:
        out.append({"ton": "neg", "text": f"Aktiva und Passiva weichen um {_euro(differenz)} € ab (Fehler in Tab)."})
    erstes = gw.erstes_bilanzjahr(conn, gewerbe_id, jahr)
    if erstes == jahr:
        n = conn.execute("SELECT COUNT(*) FROM bilanz_eroeffnung WHERE gewerbe_id = ? AND jahr = ?",
                         (gewerbe_id, jahr)).fetchone()[0]
        if not n:
            out.append({"ton": "warn", "text": "Keine Eröffnungswerte eingetragen (Kontostände, Anlagen, offene Posten "
                                               f"zum 31.12.{jahr - 1})."})
        for k in conn.execute("SELECT id, name FROM bankkonto WHERE gewerbe_id = ?", (gewerbe_id,)):
            if not conn.execute("SELECT 1 FROM bilanz_eroeffnung WHERE gewerbe_id = ? AND jahr = ? AND posten = ?",
                                (gewerbe_id, jahr, f"bank:{k['id']}")).fetchone():
                out.append({"ton": "warn", "text": f"Kontostand {k['name']} zum 31.12.{jahr - 1} fehlt in der Eröffnung."})
    v = s.get("verrechnung", 0)
    offen_u = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(betrag_cent), 0) FROM bank_umsatz WHERE gewerbe_id = ? AND datum BETWEEN ? AND ? "
        "AND buchung_id IS NULL AND status = 'offen'", (gewerbe_id, von, bis)).fetchone()
    if offen_u[0]:
        out.append({"ton": "warn", "text": f"{offen_u[0]} Bankumsätze ohne Zuordnung (zusammen {_euro(offen_u[1])} €) — "
                                           "sie stehen auf dem Verrechnungskonto.", "ziel": "/bank"})
    ohne_bank = conn.execute(
        "SELECT COUNT(*) FROM buchung b WHERE b.gewerbe_id = ? AND b.offen = 0 AND b.datum BETWEEN ? AND ? "
        "AND NOT EXISTS (SELECT 1 FROM bank_umsatz u WHERE u.buchung_id = b.id) "
        "AND EXISTS (SELECT 1 FROM bankkonto k WHERE k.gewerbe_id = b.gewerbe_id) "
        "AND EXISTS (SELECT 1 FROM buchung_position p JOIN kategorie c ON c.id = p.kategorie_id WHERE p.buchung_id = b.id "
        "AND c.key NOT IN ('fahrtkosten_kfz','wege_wohnung_betrieb','homeoffice_pauschale','verpflegungsmehraufwand',"
        "'kfz_privatnutzung','entnahme_sonstig','restbuchwert'))", (gewerbe_id, von, bis)).fetchone()[0]
    if ohne_bank:
        out.append({"ton": "warn", "text": f"{ohne_bank} bezahlte Buchungen ohne Bankumsatz — bar oder privat bezahlt? "
                                           "Dann per Abschlussbuchung gegen Kasse bzw. Privat umbuchen.", "ziel": "/buchungen"})
    if v:
        out.append({"ton": "warn", "text": f"Verrechnungskonto zum 31.12.: {_euro(v)} € (Ziel 0). Ursachen sind die Punkte "
                                           "oben, Anlagenkäufe ohne Bankumsatz oder Zahlungen, die vom Buchungsbetrag "
                                           "abweichen."})
    for a in conn.execute(
        "SELECT a.id, a.bezeichnung, a.abgang_datum FROM afa_buchung a WHERE a.gewerbe_id = ? AND a.abgang_datum BETWEEN ? "
        "AND ? AND a.afa_methode != 'sammelposten'", (gewerbe_id, von, bis)
    ):
        out.append({"ton": "warn", "text": f"Abgang „{a['bezeichnung']}“ am {a['abgang_datum']}: Restbuchwert als Buchung "
                                           "(Kategorie Restbuchwert) erfassen, sonst bleibt er im Anlagevermögen."})
    offen_b = conn.execute("SELECT COUNT(*), COALESCE(SUM(p.betrag_cent), 0) FROM buchung b JOIN buchung_position p "
                           "ON p.buchung_id = b.id WHERE b.gewerbe_id = ? AND b.offen = 1 AND b.datum <= ?",
                           (gewerbe_id, bis)).fetchone()
    if offen_b[0]:
        out.append({"ton": "leise", "text": f"{offen_b[0]} Positionen noch nicht bezahlt — stehen als Forderung bzw. "
                                            "Verbindlichkeit in der Bilanz."})
    if not out:
        out.append({"ton": "ok", "text": "Keine Auffälligkeiten."})
    return out


# ── CSV ──────────────────────────────────────────────────────────────────────

def _euro(cent: int) -> str:
    return f"{cent / 100:.2f}".replace(".", ",")


def csv_text(db: sqlite3.Connection, gewerbe_id: int, jahr: int, name: str) -> str:
    a = auswertung(db, gewerbe_id, jahr)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow([f"Bilanz und GuV {jahr} – {name} (Entwurf aus Tab, keine Steuerberatung)"])
    w.writerow([])
    w.writerow(["Gewinn- und Verlustrechnung", "", "EUR"])
    for p in a["guv"]:
        w.writerow([p["nr"], p["name"], _euro(p["betrag_cent"] if p["ertrag"] else -p["betrag_cent"])])
    w.writerow(["17.", "Jahresergebnis", _euro(a["ergebnis_cent"])])
    for h in a["hinzurechnungen"]:
        w.writerow(["", f"außerbilanziell: {h['text']}", _euro(h["betrag_cent"])])
    w.writerow(["", "Steuerlicher Gewinn", _euro(a["steuerlicher_gewinn_cent"])])
    w.writerow([])
    for titel, seite, summe in (("Aktiva", a["aktiva"], a["summe_aktiva_cent"]),
                                ("Passiva", a["passiva"], a["summe_passiva_cent"])):
        w.writerow([f"Bilanz zum 31.12.{jahr} – {titel}", "", "EUR"])
        for p in seite:
            w.writerow([p["name"], "", _euro(p["betrag_cent"])])
            for k in p["konten"]:
                w.writerow(["", k["name"], _euro(k["betrag_cent"])])
        w.writerow([f"Summe {titel}", "", _euro(summe)])
        w.writerow([])
    if a["uebergangsgewinn_cent"] is not None:
        w.writerow(["Übergangsgewinn (R 4.6 EStR, Hinweis)", "", _euro(a["uebergangsgewinn_cent"])])
    w.writerow(["Abstimmung"])
    for x in a["abstimmung"]:
        w.writerow(["", x["text"]])
    w.writerow([])
    w.writerow(["Journal"])
    w.writerow(["Datum", "Soll", "Haben", "Betrag EUR", "Text", "Beleg"])
    for z in journal(db, gewerbe_id, jahr):
        w.writerow([z["datum"], konto_name(db, z["soll"]), konto_name(db, z["haben"]), _euro(z["betrag_cent"]),
                    z["text"], z["ref"] or ""])
    return buf.getvalue()


def heute() -> str:
    return dt.date.today().isoformat()
