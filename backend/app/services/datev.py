"""DATEV-Export: Buchungsstapel im DATEV-Format (EXTF, Formatversion 13) für die Steuerberatung.

Eine Datei je Gewerbe und Jahr (DATEV verlangt einen Stapel innerhalb eines Wirtschaftsjahres). Aufbau:
Kopfzeile (31 Felder), Spaltenüberschriften (125 Felder), je Buchungszeile ein Datensatz; Trenner `;`, Text in `"`,
Zeichensatz Windows-1252, Zeilenende CRLF, Beträge positiv mit Komma, Soll/Haben-Kennzeichen getrennt.

Kontierung (Vorschlag, die Steuerberatung kann umkontieren): je Tab-Kategorie ein Sachkonto im SKR03 oder SKR04
(`KONTEN`, abgeglichen mit den DATEV-Kontenrahmen SKR03/SKR04, Stand 01/2023). Gegenkonto = Bank (SKR03 1200 /
SKR04 1800); Pauschalen ohne Geldfluss (km-Pauschale, Entfernungspauschale, Homeoffice-Pauschale,
Verpflegungsmehraufwand) gegen Privateinlage, Nutzungs-/Sachentnahmen gegen Privatentnahme, Restbuchwert gegen das
Anlagenkonto. Tab weiß nicht, ob eine Buchung bar oder privat bezahlt wurde — die Steuerberatung sieht es am Text.

  * Privatanteil (`privat_bp`): der private Teil geht als eigene Zeile auf Privatentnahmen, nur der betriebliche Teil
    auf das Aufwandskonto.
  * Bewirtung: betrieblicher Betrag 70 % auf „Bewirtungskosten“, 30 % auf „Nicht abzugsfähige Bewirtungskosten“.
  * Regelbesteuerung: Erlöse zu 19/7 % auf die Automatikkonten (8400/8300 bzw. 4400/4300, ohne BU-Schlüssel),
    Ausgaben mit Steuerschlüssel 9 (Vorsteuer 19 %) bzw. 8 (7 %). DATEV rechnet die Steuer selbst aus dem Brutto.
    Kleinunternehmer-Jahre: nie ein Steuerschlüssel, keine Automatikkonten mit Steuer.
  * Anlagen (AfA): im Anschaffungsjahr der Zugang (Anlagenkonto an Bank), jedes Jahr die AfA (AfA-Konto an
    Anlagenkonto) zum 31.12. bzw. Abgangstag — gerechnet von `services/afa.afa_jahr`, wie im Summenblatt.
  * Belegfeld 1 = Tab-Buchungsnummer („T123“), Beleginfo = Dateinamen der Belege (die Dateien selbst stehen im
    Jahres-ZIP). Belegbilder per DATEV-XML (Belegverknüpfung) sind nicht gebaut.
"""
from __future__ import annotations

import datetime as dt
import io
import sqlite3

from . import besteuerung as best
from .afa import afa_jahr
from .privatanteil import privat_cent

SPALTEN = [
    "Umsatz (ohne Soll/Haben-Kz)", "Soll/Haben-Kennzeichen", "WKZ Umsatz", "Kurs", "Basis-Umsatz",
    "WKZ Basis-Umsatz", "Kontonummer", "Gegenkonto (ohne BU-Schlüssel)", "BU-Schlüssel", "Belegdatum", "Belegfeld 1",
    "Belegfeld 2", "Skonto", "Buchungstext", "Postensperre", "Diverse Adressnummer", "Geschäftspartnerbank",
    "Sachverhalt", "Zinssperre", "Beleglink", "Beleginfo - Art 1", "Beleginfo - Inhalt 1", "Beleginfo - Art 2",
    "Beleginfo - Inhalt 2", "Beleginfo - Art 3", "Beleginfo - Inhalt 3", "Beleginfo - Art 4", "Beleginfo - Inhalt 4",
    "Beleginfo - Art 5", "Beleginfo - Inhalt 5", "Beleginfo - Art 6", "Beleginfo - Inhalt 6", "Beleginfo - Art 7",
    "Beleginfo - Inhalt 7", "Beleginfo - Art 8", "Beleginfo - Inhalt 8", "Kost 1 - Kostenstelle",
    "Kost 2 - Kostenstelle", "Kost-Menge", "EU-Land u. UStID (Bestimmung)", "EU-Steuersatz (Bestimmung)",
    "Abw. Versteuerungsart", "Sachverhalt L+L", "Funktionsergänzung L+L", "BU 49 Hauptfunktionstyp",
    "BU 49 Hauptfunktionsnummer", "BU 49 Funktionsergänzung", "Zusatzinformation - Art 1",
    "Zusatzinformation- Inhalt 1", "Zusatzinformation - Art 2", "Zusatzinformation- Inhalt 2",
    "Zusatzinformation - Art 3", "Zusatzinformation- Inhalt 3", "Zusatzinformation - Art 4",
    "Zusatzinformation- Inhalt 4", "Zusatzinformation - Art 5", "Zusatzinformation- Inhalt 5",
    "Zusatzinformation - Art 6", "Zusatzinformation- Inhalt 6", "Zusatzinformation - Art 7",
    "Zusatzinformation- Inhalt 7", "Zusatzinformation - Art 8", "Zusatzinformation- Inhalt 8",
    "Zusatzinformation - Art 9", "Zusatzinformation- Inhalt 9", "Zusatzinformation - Art 10",
    "Zusatzinformation- Inhalt 10", "Zusatzinformation - Art 11", "Zusatzinformation- Inhalt 11",
    "Zusatzinformation - Art 12", "Zusatzinformation- Inhalt 12", "Zusatzinformation - Art 13",
    "Zusatzinformation- Inhalt 13", "Zusatzinformation - Art 14", "Zusatzinformation- Inhalt 14",
    "Zusatzinformation - Art 15", "Zusatzinformation- Inhalt 15", "Zusatzinformation - Art 16",
    "Zusatzinformation- Inhalt 16", "Zusatzinformation - Art 17", "Zusatzinformation- Inhalt 17",
    "Zusatzinformation - Art 18", "Zusatzinformation- Inhalt 18", "Zusatzinformation - Art 19",
    "Zusatzinformation- Inhalt 19", "Zusatzinformation - Art 20", "Zusatzinformation- Inhalt 20", "Stück", "Gewicht",
    "Zahlweise", "Forderungsart", "Veranlagungsjahr", "Zugeordnete Fälligkeit", "Skontotyp", "Auftragsnummer",
    "Buchungstyp (Anzahlungen)", "USt-Schlüssel (Anzahlungen)", "EU-Land (Anzahlungen)",
    "Sachverhalt L+L (Anzahlungen)", "EU-Steuersatz (Anzahlungen)", "Erlöskonto (Anzahlungen)", "Herkunft-Kz",
    "Buchungs GUID", "Kost-Datum", "SEPA-Mandatsreferenz", "Skontosperre", "Gesellschaftername", "Beteiligtennummer",
    "Identifikationsnummer", "Zeichnernummer", "Postensperre bis", "Bezeichnung SoBil-Sachverhalt",
    "Kennzeichen SoBil-Buchung", "Festschreibung", "Leistungsdatum", "Datum Zuord. Steuerperiode", "Fälligkeit",
    "Generalumkehr (GU)", "Steuersatz", "Land", "Abrechnungsreferenz", "BVV-Position", "EU-Land u. UStID (Ursprung)",
    "EU-Steuersatz (Ursprung)", "Abw. Skontokonto",
]

# key -> (SKR03, SKR04)
KONTEN: dict[str, tuple[str, str]] = {
    "einnahme_ku": ("8195", "4185"),            # Erlöse als Kleinunternehmer § 19 Abs. 1 UStG
    "einnahme_steuerfrei": ("8100", "4100"),    # Steuerfreie Umsätze § 4 Nr. 8 ff. UStG
    "ust_erstattung": ("1780", "3820"),         # Umsatzsteuer-Vorauszahlungen
    "ust_zahlung": ("1780", "3820"),
    "waren": ("3200", "5200"),                  # Wareneingang
    "fremdleistungen": ("3100", "5900"),        # Fremdleistungen
    "personal": ("4120", "6020"),               # Gehälter
    "afa_beweglich": ("4830", "6220"),          # Abschreibungen auf Sachanlagen
    "gwg": ("4855", "6260"),                    # Sofortabschreibung GWG
    "restbuchwert": ("2310", "6895"),           # Anlagenabgänge Sachanlagen (Restbuchwert bei Buchverlust)
    "miete_raeume": ("4210", "6310"),           # Miete (unbewegliche Wirtschaftsgüter)
    "grundstueck_sonstige": ("4290", "6350"),   # Grundstücksaufwendungen, betrieblich
    "telekommunikation": ("4920", "6805"),      # Telefon
    "versicherungen_betrieb": ("4360", "6400"), # Versicherungen
    "miete_leasing_bwg": ("4960", "6835"),      # Mieten für Einrichtungen (bewegliche Wirtschaftsgüter)
    "wartung_reparatur": ("4805", "6470"),      # Reparaturen und Instandhaltung BGA
    "rechts_steuer_buchfuehrung": ("4950", "6825"),  # Rechts- und Beratungskosten
    "fortbildung": ("4945", "6821"),            # Fortbildungskosten
    "werbung_repraesentation": ("4600", "6600"),  # Werbekosten
    "reise_nebenkosten": ("4676", "6680"),      # Reisekosten Unternehmer Übernachtung/Nebenkosten
    "software_hosting": ("4964", "6837"),       # Zeitlich befristete Überlassung von Rechten (Lizenzen)
    "buerobedarf": ("4930", "6815"),            # Bürobedarf
    "gebuehren_abgaben": ("4390", "6430"),      # Sonstige Abgaben
    "kontogebuehren": ("4970", "6855"),         # Nebenkosten des Geldverkehrs
    "geschenke": ("4630", "6610"),              # Geschenke abzugsfähig ohne § 37b EStG
    "bewirtung": ("4650", "6640"),              # Bewirtungskosten (70 %)
    "verpflegungsmehraufwand": ("4674", "6674"),  # Reisekosten Unternehmer Verpflegungsmehraufwand
    "arbeitszimmer": ("4288", "6348"),          # Häusliches Arbeitszimmer (abziehbarer Anteil)
    "homeoffice_pauschale": ("4900", "6300"),   # Sonstige betriebliche Aufwendungen
    "fahrtkosten_kfz": ("4673", "6673"),        # Reisekosten Unternehmer Fahrtkosten
    "wege_wohnung_betrieb": ("4678", "6688"),   # Fahrten Wohnung–Betriebsstätte (abziehbarer Anteil)
    "kfz_kosten": ("4530", "6530"),             # Laufende Fahrzeug-Betriebskosten
    "oepnv": ("4673", "6673"),                  # Reisekosten Unternehmer Fahrtkosten
    "zinsen": ("2100", "7300"),                 # Zinsen und ähnliche Aufwendungen
}
# Je nach Steuersatz: (mit 19 % USt — Automatikkonto, ohne/0 %)
KONTEN_MIT_UST: dict[str, tuple[tuple[str, str], tuple[str, str]]] = {
    "einnahme_ust": (("8400", "4400"), ("8200", "4200")),
    "veraeusserung_av": (("8820", "4845"), ("8829", "4849")),
    "kfz_privatnutzung": (("8921", "4645"), ("8924", "4639")),
    "entnahme_sonstig": (("8910", "4620"), ("8905", "4605")),
}
ERLOESE_7 = ("8300", "4300")
BEWIRTUNG_NICHT_ABZUGSFAEHIG = ("4654", "6644")
BANK = ("1200", "1800")
PRIVATENTNAHME = ("1800", "2100")
PRIVATEINLAGE = ("1890", "2180")
ANLAGE = ("0490", "0690")          # Sonstige Betriebs- und Geschäftsausstattung
SAMMELPOSTEN = ("0485", "0675")
AFA_SAMMELPOSTEN = ("4862", "6264")
GEGEN_PRIVATEINLAGE = {"fahrtkosten_kfz", "wege_wohnung_betrieb", "homeoffice_pauschale", "verpflegungsmehraufwand"}
GEGEN_PRIVATENTNAHME = {"kfz_privatnutzung", "entnahme_sonstig"}
VORSTEUER_SCHLUESSEL = {1900: "9", 700: "8"}


class DatevFehler(ValueError):
    pass


def _k(paar: tuple[str, str], skr: str) -> str:
    return paar[0] if skr == "03" else paar[1]


def _betrag(cent: int) -> str:
    return f"{cent // 100},{cent % 100:02d}"


def _text(s) -> str:
    return '"' + str(s or "").replace('"', '""').replace("\r", " ").replace("\n", " ") + '"'


class _Stapel:
    def __init__(self, skr: str):
        self.skr = skr
        self.zeilen: list[list[str]] = []
        self.hinweise: list[str] = []

    def add(self, *, betrag: int, sh: str, konto: str, gegen: str, datum: str, beleg: str, text: str,
            bu: str = "", beleginfo: str = "") -> None:
        if betrag <= 0:
            return
        z = [""] * len(SPALTEN)
        z[0] = _betrag(betrag)
        z[1] = _text(sh)
        z[2] = _text("EUR")
        z[6] = konto
        z[7] = gegen
        z[8] = _text(bu)
        z[9] = datum[8:10] + datum[5:7]          # Belegdatum TTMM
        z[10] = _text(beleg[:36])
        z[13] = _text(text[:60])
        if beleginfo:
            z[20] = _text("Tab-Belege")
            z[21] = _text(beleginfo[:210])
        self.zeilen.append(z)


def einstellungen(gewerbe: sqlite3.Row) -> tuple[int, int, str]:
    if not gewerbe["datev_berater"] or not gewerbe["datev_mandant"]:
        raise DatevFehler("Für den DATEV-Export fehlen Berater- und Mandantennummer — im Gewerbe unter „DATEV“ eintragen "
                          "(beides bekommst du von deiner Steuerberatung).")
    return int(gewerbe["datev_berater"]), int(gewerbe["datev_mandant"]), gewerbe["datev_skr"] or "03"


def stapel(conn: sqlite3.Connection, gewerbe_id: int, jahr: int) -> _Stapel:
    g = conn.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    _, _, skr = einstellungen(g)
    regel = best.ist_regel(conn, gewerbe_id, jahr)
    st = _Stapel(skr)
    bank = _k(BANK, skr)
    belege: dict[int, list[str]] = {}
    for r in conn.execute(
        "SELECT b.buchung_id, b.original_name FROM beleg b JOIN buchung x ON x.id = b.buchung_id "
        "WHERE x.gewerbe_id = ? AND substr(x.datum,1,4) = ? ORDER BY b.id", (gewerbe_id, str(jahr)),
    ):
        belege.setdefault(r["buchung_id"], []).append(r["original_name"] or "")

    for p in conn.execute(
        "SELECT b.id AS bid, b.datum, b.beschreibung, p.betrag_cent, p.privat_bp, p.ust_bp, p.ust_cent, "
        "k.key, k.name, k.typ FROM buchung_position p JOIN buchung b ON b.id = p.buchung_id "
        "JOIN kategorie k ON k.id = p.kategorie_id WHERE b.gewerbe_id = ? AND substr(b.datum,1,4) = ? "
        "ORDER BY b.datum, b.id, p.id", (gewerbe_id, str(jahr)),
    ):
        key, brutto, satz = p["key"], p["betrag_cent"], (p["ust_bp"] or 0) if regel else 0
        beleg = f"T{p['bid']}"
        text = p["beschreibung"] or p["name"]
        info = ", ".join(belege.get(p["bid"], []))
        einnahme = p["typ"] == "einnahme"
        if key in KONTEN_MIT_UST:
            mit, ohne = KONTEN_MIT_UST[key]
            if satz == 1900:
                konto = _k(mit, skr)
            elif satz == 700 and key == "einnahme_ust":
                konto = _k(ERLOESE_7, skr)
            else:
                konto = _k(ohne, skr)
                if satz:
                    st.hinweise.append(f"{p['datum']} „{text}“: Steuersatz {satz / 100:g} % — ohne Steuerschlüssel "
                                       f"auf {konto} exportiert, bitte prüfen.")
        elif key in KONTEN:
            konto = _k(KONTEN[key], skr)
        else:
            konto = "9999"
            st.hinweise.append(f"Kategorie „{p['name']}“ hat kein DATEV-Konto (Konto 9999) — bitte umkontieren.")
        gegen = (_k(PRIVATEINLAGE, skr) if key in GEGEN_PRIVATEINLAGE else
                 _k(PRIVATENTNAHME, skr) if key in GEGEN_PRIVATENTNAHME else
                 _k(ANLAGE, skr) if key == "restbuchwert" else bank)
        sh = "H" if einnahme else "S"
        # Steuerschlüssel nur auf Aufwandskonten ohne Automatik (Erlöse laufen über Automatikkonten)
        bu = VORSTEUER_SCHLUESSEL.get(satz, "") if (regel and not einnahme and key not in ("ust_zahlung",)) else ""
        if regel and not einnahme and satz and satz not in VORSTEUER_SCHLUESSEL:
            st.hinweise.append(f"{p['datum']} „{text}“: Vorsteuersatz {satz / 100:g} % — ohne Steuerschlüssel exportiert.")
        betrieblich = brutto
        if not einnahme and p["privat_bp"]:
            privat = privat_cent(brutto, p["privat_bp"])
            betrieblich = brutto - privat
            st.add(betrag=privat, sh="S", konto=_k(PRIVATENTNAHME, skr), gegen=gegen, datum=p["datum"], beleg=beleg,
                   text=f"{text} (Privatanteil {p['privat_bp'] / 100:g} %)", beleginfo=info)
        if key == "bewirtung":
            abzug = round(betrieblich * 0.7)
            st.add(betrag=abzug, sh=sh, konto=konto, gegen=gegen, datum=p["datum"], beleg=beleg, text=text, bu=bu,
                   beleginfo=info)
            st.add(betrag=betrieblich - abzug, sh=sh, konto=_k(BEWIRTUNG_NICHT_ABZUGSFAEHIG, skr), gegen=gegen,
                   datum=p["datum"], beleg=beleg, text=f"{text} (30 % nicht abzugsfähig)", bu=bu, beleginfo=info)
        else:
            st.add(betrag=betrieblich, sh=sh, konto=konto, gegen=gegen, datum=p["datum"], beleg=beleg, text=text, bu=bu,
                   beleginfo=info)

    # Anlagen: Zugang im Anschaffungsjahr, AfA je Jahr
    for a in conn.execute("SELECT * FROM afa_buchung WHERE gewerbe_id = ? ORDER BY anschaffungsdatum, id", (gewerbe_id,)):
        sammel = a["afa_methode"] == "sammelposten"
        anlage = _k(SAMMELPOSTEN if sammel else ANLAGE, skr)
        if a["anschaffungsdatum"][:4] == str(jahr):
            vst = a["vorsteuer_cent"] if regel else 0
            st.add(betrag=a["anschaffungskosten_cent"] + vst, sh="S", konto=anlage, gegen=bank, datum=a["anschaffungsdatum"],
                   beleg=f"A{a['id']}", text=f"Zugang {a['bezeichnung']}", bu="9" if vst else "")
        betrag = afa_jahr(a, jahr)
        if betrag > 0:
            ende = a["abgang_datum"] if (a["abgang_datum"] and a["abgang_datum"][:4] == str(jahr) and not sammel) else f"{jahr}-12-31"
            st.add(betrag=betrag, sh="S", konto=_k(AFA_SAMMELPOSTEN if sammel else KONTEN["afa_beweglich"], skr),
                   gegen=anlage, datum=ende, beleg=f"A{a['id']}", text=f"AfA {jahr} {a['bezeichnung']}")
    return st


def buchungsstapel_csv(conn: sqlite3.Connection, gewerbe_id: int, jahr: int, jetzt: dt.datetime | None = None) -> bytes:
    g = conn.execute("SELECT * FROM gewerbe WHERE id = ?", (gewerbe_id,)).fetchone()
    berater, mandant, skr = einstellungen(g)
    st = stapel(conn, gewerbe_id, jahr)
    jetzt = jetzt or dt.datetime.now()
    kopf = [
        _text("EXTF"), "700", "21", _text("Buchungsstapel"), "13",
        jetzt.strftime("%Y%m%d%H%M%S") + f"{jetzt.microsecond // 1000:03d}", "", _text("RE"), _text("Tab"), _text(""),
        str(berater), str(mandant), f"{jahr}0101", "4", f"{jahr}0101", f"{jahr}1231",
        _text(f"Tab {g['name']} {jahr}"[:30]), _text(""), "1", "0", "0", _text("EUR"), "", _text(""), "", "",
        _text(skr), "", "", _text(""), _text(""),
    ]
    buf = io.StringIO()
    buf.write(";".join(kopf) + "\r\n")
    buf.write(";".join(SPALTEN) + "\r\n")
    for z in st.zeilen:
        buf.write(";".join(z) + "\r\n")
    return buf.getvalue().encode("cp1252", "replace")
