"""Digitale Eigenbelege (v42): Ersatz, wenn ein Fremdbeleg fehlt oder es nie einen gab.

Grundlage: GoBD Rz. 61 („Ist kein Fremdbeleg vorhanden, muss ein Eigenbeleg erstellt werden.“) und
Rz. 77 (Beleginhalte: Belegnummer, Aussteller/Empfänger, Betrag, Belegdatum, Erläuterung, verantwortlicher
Aussteller). Für die digitale Form ohne Unterschrift auf Papier stützt sich Tab auf das BMF-Schreiben vom
19.11.2025 zu Bewirtungskosten (Rn. 19, 22): Autorisierung durch elektronische Genehmigung, Zeitpunkt
elektronisch aufgezeichnet, Angaben nicht undokumentiert änderbar. Das Schreiben gilt ausdrücklich nur für
Bewirtungsbelege — für andere Eigenbelege ist es eine Übertragung, keine ausdrückliche Regel (EUER_KATEGORIEN.md §10).

So setzt Tab das um: die Angaben werden beim Erstellen eingefroren (PDF + JSON in `beleg.eigenbeleg`, mit
SHA-256 der Angaben), es gibt keinen Weg sie zu ändern (nur löschen und neu erstellen, beides im
Änderungsprotokoll), Freigabe = Bestätigung durch den angemeldeten Inhaber mit Zeitstempel.
Die Datei läuft über `beleg_store.speichere_beleg` — Jahres-Sperre, Siegel und Backup greifen wie bei jedem Beleg.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import sqlite3
from zoneinfo import ZoneInfo

from fpdf import FPDF

from . import besteuerung
from .export import _date_de
from .girocode import absender_name
from .rechnung_pdf import INK, LINE, MUTED, ROYAL, latin1

BERLIN = ZoneInfo("Europe/Berlin")

GRUENDE = {
    "verloren": "Originalbeleg ist verloren gegangen",
    "nicht_erhalten": "Es wurde kein Beleg ausgegeben (z. B. Automat, Trinkgeld, Kleinbetrag)",
    "unleserlich": "Originalbeleg ist unleserlich oder beschädigt",
    "sonstiges": "Sonstiger Grund",
}
ZAHLUNGSARTEN = {
    "bar": "Bar",
    "karte": "Karte",
    "ueberweisung": "Überweisung / Lastschrift",
    "sonstiges": "Sonstige",
}

# Weiche Grenzen — gesetzlich gibt es keine Höchstbeträge; Prüfer sehen hohe Beträge und Häufungen kritisch.
HOHER_BETRAG_CENT = 15000
VIELE_JE_JAHR = 12


class EigenbelegFehler(ValueError):
    """Eingabe passt nicht — Meldung ist nutzertauglich."""


def anzahl_im_jahr(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM beleg WHERE gewerbe_id = ? AND eigenbeleg IS NOT NULL "
        "AND json_extract(eigenbeleg, '$.datum') LIKE ?",
        (gewerbe_id, f"{jahr}-%"),
    ).fetchone()[0]


def naechste_nummer(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> str:
    """EB-{jahr}-{lauf:04d}, fortlaufend je Gewerbe + Jahr des Ausgabedatums. Gelöschte Nummern werden nicht
    wiederverwendet (höchste vergebene + 1)."""
    row = conn.execute(
        "SELECT MAX(CAST(substr(json_extract(eigenbeleg, '$.nummer'), 9) AS INTEGER)) FROM beleg "
        "WHERE gewerbe_id = ? AND json_extract(eigenbeleg, '$.nummer') LIKE ?",
        (gewerbe_id, f"EB-{jahr}-%"),
    ).fetchone()
    return f"EB-{jahr}-{(row[0] or 0) + 1:04d}"


def hinweise(
    conn: sqlite3.Connection,
    gewerbe_id: int,
    *,
    datum: str | None,
    betrag_cent: int | None,
    buchung_id: int | None = None,
    kategorie_key: str | None = None,
) -> list[dict]:
    """Weiche Hinweise (nie blockierend): {ton: 'warn'|'leise', text}."""
    out: list[dict] = []
    jahr = None
    try:
        jahr = dt.date.fromisoformat(datum).year if datum else None
    except ValueError:
        jahr = None
    keys: set[str] = {kategorie_key} if kategorie_key else set()
    hat_ust = False
    if buchung_id:
        for p in conn.execute(
            "SELECT k.key, p.ust_cent FROM buchung_position p JOIN kategorie k ON k.id = p.kategorie_id "
            "WHERE p.buchung_id = ?",
            (buchung_id,),
        ):
            keys.add(p["key"])
            hat_ust = hat_ust or bool(p["ust_cent"])
    if jahr and besteuerung.art(conn, gewerbe_id, jahr) == besteuerung.REGEL:
        out.append({
            "ton": "warn",
            "text": "Regelbesteuerung: Aus einem Eigenbeleg gibt es keinen Vorsteuerabzug (§ 15 UStG verlangt eine "
                    "Rechnung). Buche die Ausgabe brutto ohne Steuer (0 %)."
                    + (" Die Buchung enthält Vorsteuer — bitte auf 0 % ändern." if hat_ust else ""),
        })
    if "bewirtung" in keys:
        out.append({
            "ton": "warn",
            "text": "Bewirtung in einer Gaststätte: Die maschinelle Rechnung des Restaurants ist Pflicht. Ein "
                    "Eigenbeleg ersetzt sie nicht, er ergänzt nur Anlass und Teilnehmer.",
        })
    if betrag_cent and betrag_cent > HOHER_BETRAG_CENT:
        out.append({
            "ton": "warn",
            "text": "Hoher Betrag für einen Eigenbeleg. Frag wenn möglich beim Händler nach einer Rechnungskopie "
                    "und heb den Zahlungsnachweis (Kontoauszug) auf — bei großen Beträgen wird ein Eigenbeleg "
                    "kritischer geprüft.",
        })
    if jahr and anzahl_im_jahr(conn, gewerbe_id, jahr) >= VIELE_JE_JAHR:
        out.append({
            "ton": "leise",
            "text": f"Schon {anzahl_im_jahr(conn, gewerbe_id, jahr)} Eigenbelege in {jahr}. Eigenbelege sind die "
                    "Ausnahme — eine Häufung fällt bei einer Prüfung auf.",
        })
    return out


def angaben_hash(angaben: dict) -> str:
    roh = json.dumps(angaben, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(roh.encode("utf-8")).hexdigest()


def jetzt() -> str:
    return dt.datetime.now(BERLIN).replace(microsecond=0).isoformat()


def _euro(cent: int) -> str:
    s = f"{cent / 100:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") + " EUR"


def pdf(eb: dict, gewerbe: sqlite3.Row) -> bytes:
    """A4-Eigenbeleg im Briefbogen-Stil der Rechnung (Core-Font, alles Nutzertext durch latin1)."""
    p = FPDF(format="A4")
    p.set_auto_page_break(True, margin=18)
    p.set_margins(20, 18, 20)
    p.add_page()
    p.set_title(latin1(f"Eigenbeleg {eb['nummer']}"))
    p.set_creator("Tab")

    p.set_text_color(*ROYAL)
    p.set_font("Helvetica", "B", 9)
    p.cell(0, 5, "EIGENBELEG", new_x="LMARGIN", new_y="NEXT")
    p.set_text_color(*INK)
    p.set_font("Helvetica", "B", 20)
    p.cell(0, 10, latin1(f"Ersatzbeleg {eb['nummer']}"), new_x="LMARGIN", new_y="NEXT")
    p.set_font("Helvetica", "", 9)
    p.set_text_color(*MUTED)
    p.multi_cell(0, 4.5, latin1(
        "Eigenbeleg nach GoBD Rz. 61, weil kein Fremdbeleg vorliegt. Kein Vorsteuerabzug aus diesem Beleg."
    ), new_x="LMARGIN", new_y="NEXT")
    p.ln(4)

    aussteller = [absender_name(gewerbe)] + [
        z.strip() for z in (gewerbe["anschrift"] or "").splitlines()[1:] if z.strip()
    ]

    def zeile(label: str, wert: str, fett: bool = False):
        p.set_draw_color(*LINE)
        y = p.get_y()
        p.line(20, y, 190, y)
        p.ln(1.5)
        p.set_font("Helvetica", "", 8.5)
        p.set_text_color(*MUTED)
        p.cell(52, 5.5, latin1(label))
        p.set_font("Helvetica", "B" if fett else "", 11 if fett else 10)
        p.set_text_color(*INK)
        p.multi_cell(0, 5.5, latin1(wert or "-"), new_x="LMARGIN", new_y="NEXT")
        p.ln(1.5)

    zeile("Betrag", _euro(eb["betrag_cent"]), fett=True)
    zeile("Datum der Ausgabe", _date_de(eb["datum"]))
    zeile("Zahlungsempfänger", eb["empfaenger"])
    zeile("Was wurde bezahlt", eb["gegenstand"])
    zeile("Betrieblicher Anlass", eb["anlass"])
    zeile("Zahlungsart", ZAHLUNGSARTEN.get(eb.get("zahlungsart") or "", "-"))
    grund = GRUENDE.get(eb["grund"], eb["grund"])
    if eb.get("grund_text"):
        grund = f"{grund}: {eb['grund_text']}"
    zeile("Warum kein Originalbeleg", grund)
    zeile("Aussteller (Unternehmen)", "\n".join(aussteller) + (f"\nSt.-Nr. {gewerbe['steuernummer']}"
                                                              if gewerbe["steuernummer"] else ""))
    erstellt = dt.datetime.fromisoformat(eb["erstellt_am"])
    zeile("Erstellt am", erstellt.strftime("%d.%m.%Y, %H:%M Uhr"))
    p.set_draw_color(*LINE)
    p.line(20, p.get_y(), 190, p.get_y())
    p.ln(6)

    p.set_font("Helvetica", "B", 10)
    p.set_text_color(*INK)
    p.cell(0, 5.5, latin1("Erklärung und elektronische Freigabe"),
           new_x="LMARGIN", new_y="NEXT")
    p.set_font("Helvetica", "", 9.5)
    p.multi_cell(0, 5, latin1(
        "Ich bestätige, dass die Ausgabe wie angegeben betrieblich angefallen ist, dass kein Originalbeleg "
        "vorliegt und dass ich sie nicht anderweitig geltend mache."
    ), new_x="LMARGIN", new_y="NEXT")
    p.ln(2)
    p.set_text_color(*MUTED)
    p.set_font("Helvetica", "", 8.5)
    p.multi_cell(0, 4.5, latin1(
        f"Elektronisch freigegeben von {eb['erstellt_von']} am {erstellt.strftime('%d.%m.%Y um %H:%M:%S Uhr')} "
        f"(angemeldet in Tab). Die Angaben sind nach der Freigabe nicht mehr änderbar; Löschen und Neuerstellen "
        f"stehen im Änderungsprotokoll.\nPrüfwert der Angaben (SHA-256): {eb['pruefwert']}"
    ), new_x="LMARGIN", new_y="NEXT")
    return bytes(p.output())
