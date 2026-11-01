"""Idempotenter Stammdaten-Seed (Upsert) — Quelle: EUER_KATEGORIEN.md.

Stammdaten (kategorie, euer_jahr, euer_zeile, euer_mapping) werden per
ON CONFLICT DO UPDATE geseedet, damit Mapping-Korrekturen einfach deploybar sind.
Nutzerdaten (gewerbe, buchung, afa_buchung) werden NICHT angefasst.

Mapping ist jahres-versioniert, Zeilen und Mapping gelten je Jahr:
- 2025: Anlage EÜR 2025 (BMF-Schreiben vom 29.08.2025).
- 2026: Anlage EÜR 2026 (BMF-Schreiben vom 01.09.2026). Neue Zeile 27 (Rücklage
  Tierbewertung, nur Land-/Forstwirte) — dadurch rutschen fast alle Zeilen ab 29 nach hinten.

Nie befüllte Zeilen (Kleinunternehmer = brutto): Zeilen 15 und 17 sowie Vorsteuer und
an das Finanzamt gezahlte USt (2025: 57/58, 2026: 58/59).
"""
from __future__ import annotations

import sqlite3

# Zeilen, die bei Kleinunternehmern niemals befüllt werden (Guard im Export), je Jahr.
NIE_BEFUELLT_JE_JAHR: dict[int, set[int]] = {
    2025: {15, 17, 57, 58},
    2026: {15, 17, 58, 59},
}


def nie_befuellt(jahr: int) -> set[int]:
    return NIE_BEFUELLT_JE_JAHR.get(jahr, set())


# (key, name, typ, abzug_quote, ist_afa, belegpflicht_extra, sort_order)
KATEGORIEN: list[tuple] = [
    # --- Einnahmen ---
    ("einnahme_ku",        "Einnahme Kleinunternehmer (z. B. App-/IAP-Erlöse)", "einnahme", 1.0, 0, 0, 10),
    ("einnahme_steuerfrei","Umsatzsteuerfreie Einnahme §4 Nr. 11 (Courtage)",   "einnahme", 1.0, 0, 0, 11),
    ("veraeusserung_av",   "Veräußerung/Entnahme Anlagevermögen",               "einnahme", 1.0, 0, 0, 12),
    ("kfz_privatnutzung",  "Private Kfz-Nutzung (1 %-Regelung, Betriebs-Kfz)",  "einnahme", 1.0, 0, 0, 13),
    ("entnahme_sonstig",   "Sonstige Entnahmen (Sach-/Nutzungs-/Leistungsentnahme)", "einnahme", 1.0, 0, 0, 14),
    # --- Ausgaben: Wareneinsatz/Fremdleistungen ---
    ("waren",              "Waren / Roh- und Hilfsstoffe",                       "ausgabe", 1.0, 0, 0, 20),
    ("fremdleistungen",    "Bezogene Leistungen / Fremdleistungen / Provisionen","ausgabe", 1.0, 0, 0, 21),
    ("personal",           "Personal: Löhne, Gehälter, Minijob-Pauschalabgaben", "ausgabe", 1.0, 0, 0, 21),
    # --- Ausgaben: AfA / GWG ---
    ("afa_beweglich",      "AfA bewegliche Wirtschaftsgüter (Hardware > 800 €)", "ausgabe", 1.0, 1, 0, 22),
    ("gwg",                "GWG-Sofortabzug (≤ 800 € netto)",                    "ausgabe", 1.0, 0, 0, 23),
    ("restbuchwert",       "Restbuchwert ausgeschiedener Anlagegüter",           "ausgabe", 1.0, 0, 0, 24),
    # --- Ausgaben: Raumkosten ---
    ("miete_raeume",       "Miete betrieblich genutzte Räume",                   "ausgabe", 1.0, 0, 0, 25),
    ("grundstueck_sonstige","Sonstige Grundstücksaufwendungen (betrieblich)",    "ausgabe", 1.0, 0, 0, 26),
    # --- Ausgaben: sonstige unbeschränkt abziehbar ---
    ("telekommunikation",  "Telekommunikation (Telefon, Internet)",              "ausgabe", 1.0, 0, 0, 27),
    ("versicherungen_betrieb","Versicherungen / Beiträge (betrieblich)",         "ausgabe", 1.0, 0, 0, 28),
    ("miete_leasing_bwg",  "Miete/Leasing bewegliche Wirtschaftsgüter (ohne Kfz)","ausgabe", 1.0, 0, 0, 29),
    ("wartung_reparatur",  "Wartung / Reparatur / Instandhaltung",               "ausgabe", 1.0, 0, 0, 30),
    ("rechts_steuer_buchfuehrung","Rechts-/Steuerberatung, Buchführung",         "ausgabe", 1.0, 0, 0, 31),
    ("fortbildung",        "Fortbildung",                                        "ausgabe", 1.0, 0, 0, 32),
    ("werbung_repraesentation","Werbung / Repräsentation",                       "ausgabe", 1.0, 0, 0, 33),
    ("reise_nebenkosten",  "Reisekosten (Übernachtung/Nebenkosten)",             "ausgabe", 1.0, 0, 0, 34),
    ("software_hosting",   "Software / Hosting / SaaS / Domains",                 "ausgabe", 1.0, 0, 0, 35),
    ("buerobedarf",        "Bürobedarf / Porto / sonstige laufende Kosten",      "ausgabe", 1.0, 0, 0, 36),
    ("gebuehren_abgaben",  "Gebühren & Abgaben (Behörden, Gewerbeanmeldung)",    "ausgabe", 1.0, 0, 0, 36),
    ("kontogebuehren",     "Kontoführung & Zahlungsgebühren (Bank, PayPal, Stripe)", "ausgabe", 1.0, 0, 0, 37),
    # --- Ausgaben: beschränkt abziehbar ---
    ("geschenke",          "Geschenke an Geschäftspartner (≤ 50 €/Empfänger)",   "ausgabe", 1.0, 0, 1, 38),
    ("bewirtung",          "Bewirtung (geschäftlich, 70 % abziehbar)",           "ausgabe", 0.7, 0, 1, 39),
    ("verpflegungsmehraufwand","Verpflegungsmehraufwand (Reise, Pauschbeträge)", "ausgabe", 1.0, 0, 0, 40),
    ("arbeitszimmer",      "Häusliches Arbeitszimmer",                           "ausgabe", 1.0, 0, 0, 41),
    ("homeoffice_pauschale","Homeoffice-Tagespauschale (6 €/Tag)",               "ausgabe", 1.0, 0, 0, 42),
    # --- Ausgaben: Kfz / Fahrtkosten ---
    ("fahrtkosten_kfz",    "Fahrtkosten privates Kfz (0,30 €/km)",               "ausgabe", 1.0, 0, 0, 43),
    ("wege_wohnung_betrieb","Wege Wohnung–Betriebsstätte (Entfernungspauschale)","ausgabe", 1.0, 0, 0, 44),
    ("kfz_kosten",         "Kfz-Kosten Betriebs-Kfz (Benzin, Versicherung, Reparatur, Leasing)", "ausgabe", 1.0, 0, 0, 45),
    ("oepnv",              "ÖPNV / Bahn / Taxi (Geschäftsfahrten)",              "ausgabe", 1.0, 0, 0, 46),
    ("zinsen",             "Zinsen & Finanzierungskosten (betrieblich)",         "ausgabe", 1.0, 0, 0, 47),
]

# ======================================================================================
# VZ 2025 — Anlage EÜR 2025 (BMF-Schreiben 29.08.2025)
# Die laufenden Kosten (⚠) stehen bewusst auf der gewinnneutralen Zeile 60 („übrige").
# ======================================================================================

# (nummer, bezeichnung) — Zeilen-Stammdaten
ZEILEN_2025: list[tuple[int, str]] = [
    (12, "Betriebseinnahmen als umsatzsteuerlicher Kleinunternehmer (brutto)"),
    (16, "Umsatzsteuerfreie Betriebseinnahmen (§4 UStG)"),
    (19, "Veräußerung/Entnahme von Anlagevermögen"),
    (20, "Private Kfz-Nutzung (1 %-Regelung)"),
    (21, "Sonstige Sach-, Nutzungs- und Leistungsentnahmen"),
    (27, "Waren, Rohstoffe und Hilfsstoffe"),
    (29, "Bezogene Leistungen / Fremdleistungen"),
    (33, "Abschreibungen auf bewegliche Wirtschaftsgüter (AfA)"),
    (36, "Sofortabschreibung geringwertiger Wirtschaftsgüter (GWG)"),
    (38, "Restbuchwert ausgeschiedener Anlagegüter"),
    (39, "Miete/Pacht für Geschäftsräume und betrieblich genutzte Grundstücke"),
    (41, "Sonstige Grundstücksaufwendungen (betrieblich)"),
    (44, "Reisekosten (Übernachtung/Nebenkosten)"),
    (60, "Übrige unbeschränkt abziehbare Betriebsausgaben"),
    (62, "Geschenke (beschränkt abziehbar)"),
    (63, "Bewirtungsaufwendungen (70 % abziehbar)"),
    (64, "Verpflegungsmehraufwand (Pauschbeträge)"),
    (65, "Aufwendungen für häusliches Arbeitszimmer"),
    (66, "Homeoffice-Tagespauschale"),
    (71, "Fahrtkosten privates Kfz"),
    (73, "Wege Wohnung–Betriebsstätte (Entfernungspauschale)"),
]

# key -> zeilen-nummer
MAPPING_2025: dict[str, int] = {
    "einnahme_ku": 12,
    "einnahme_steuerfrei": 16,
    "veraeusserung_av": 19,
    "kfz_privatnutzung": 20,
    "entnahme_sonstig": 21,
    "waren": 27,
    "fremdleistungen": 29,
    "afa_beweglich": 33,
    "gwg": 36,
    "restbuchwert": 38,
    "miete_raeume": 39,
    "grundstueck_sonstige": 41,
    "reise_nebenkosten": 44,
    "software_hosting": 60,
    "buerobedarf": 60,
    "telekommunikation": 60,            # ⚠ gewinnneutraler Default (Vordruck: 43)
    "versicherungen_betrieb": 60,       # ⚠ (Vordruck: 49)
    "miete_leasing_bwg": 60,            # ⚠ (Vordruck: 47)
    "wartung_reparatur": 60,            # ⚠ (Vordruck: 48)
    "rechts_steuer_buchfuehrung": 60,   # ⚠ (Vordruck: 46)
    "fortbildung": 60,                  # ⚠ (Vordruck: 45)
    "werbung_repraesentation": 60,      # ⚠ (Vordruck: 54)
    "gebuehren_abgaben": 60,            # ⚠ (Vordruck: 49)
    "kontogebuehren": 60,
    "kfz_kosten": 60,                   # ⚠ (Vordruck: 70)
    "oepnv": 60,                        # ⚠ (Vordruck: 70)
    "personal": 60,                     # ⚠ (Vordruck: 30)
    "zinsen": 60,                       # ⚠ (Vordruck: 55/56)
    "geschenke": 62,
    "bewirtung": 63,
    "verpflegungsmehraufwand": 64,
    "arbeitszimmer": 65,
    "homeoffice_pauschale": 66,
    "fahrtkosten_kfz": 71,
    "wege_wohnung_betrieb": 73,
}

# ======================================================================================
# VZ 2026 — Anlage EÜR 2026 (BMF-Schreiben 01.09.2026, Vordruck 2026AnlEÜR801–803)
# Neue Zeile 27 + Übertragszeile 28 → Waren steht jetzt auf 29, ab dort meist +1 (Waren +2).
# Alle Zeilen am Vordruck geprüft, auch die laufenden Kosten sind final.
# ======================================================================================

ZEILEN_2026: list[tuple[int, str]] = [
    (12, "Betriebseinnahmen als umsatzsteuerlicher Kleinunternehmer (brutto)"),
    (16, "Umsatzsteuerfreie Betriebseinnahmen (§4 UStG)"),
    (19, "Veräußerung/Entnahme von Anlagevermögen"),
    (20, "Private Kfz-Nutzung (1 %-Regelung)"),
    (21, "Sonstige Sach-, Nutzungs- und Leistungsentnahmen"),
    (29, "Waren, Rohstoffe und Hilfsstoffe"),
    (30, "Bezogene Leistungen / Fremdleistungen"),
    (31, "Ausgaben für eigenes Personal"),
    (34, "Abschreibungen auf bewegliche Wirtschaftsgüter (AfA)"),
    (37, "Sofortabschreibung geringwertiger Wirtschaftsgüter (GWG)"),
    (39, "Restbuchwert ausgeschiedener Anlagegüter"),
    (40, "Miete/Pacht für Geschäftsräume und betrieblich genutzte Grundstücke"),
    (42, "Sonstige Grundstücksaufwendungen (betrieblich)"),
    (44, "Aufwendungen für Telekommunikation"),
    (45, "Reisekosten (Übernachtung/Nebenkosten)"),
    (46, "Fortbildungskosten"),
    (47, "Rechts- und Steuerberatung, Buchführung"),
    (48, "Miete/Leasing für bewegliche Wirtschaftsgüter (ohne Kfz)"),
    (49, "Erhaltungsaufwendungen (Instandhaltung, Wartung, Reparatur)"),
    (50, "Beiträge, Gebühren, Abgaben und Versicherungen"),
    (55, "Werbekosten"),
    (57, "Übrige Schuldzinsen"),
    (61, "Übrige unbeschränkt abziehbare Betriebsausgaben"),
    (63, "Geschenke (beschränkt abziehbar)"),
    (64, "Bewirtungsaufwendungen (70 % abziehbar)"),
    (65, "Verpflegungsmehraufwand (Pauschbeträge)"),
    (66, "Aufwendungen für häusliches Arbeitszimmer"),
    (67, "Homeoffice-Tagespauschale"),
    (71, "Sonstige tatsächliche Fahrtkosten (Kfz, Treibstoff, öffentliche Verkehrsmittel)"),
    (72, "Fahrtkosten privates Kfz (Nutzungseinlage)"),
    (74, "Wege Wohnung–Betriebsstätte (Entfernungspauschale)"),
]

MAPPING_2026: dict[str, int] = {
    "einnahme_ku": 12,
    "einnahme_steuerfrei": 16,
    "veraeusserung_av": 19,
    "kfz_privatnutzung": 20,
    "entnahme_sonstig": 21,
    "waren": 29,
    "fremdleistungen": 30,
    "personal": 31,
    "afa_beweglich": 34,
    "gwg": 37,
    "restbuchwert": 39,
    "miete_raeume": 40,
    "grundstueck_sonstige": 42,
    "telekommunikation": 44,
    "reise_nebenkosten": 45,
    "fortbildung": 46,
    "rechts_steuer_buchfuehrung": 47,
    "miete_leasing_bwg": 48,
    "wartung_reparatur": 49,
    "versicherungen_betrieb": 50,
    "gebuehren_abgaben": 50,            # „Beiträge, Gebühren, Abgaben und Versicherungen"
    "werbung_repraesentation": 55,
    "zinsen": 57,                       # „Übrige Schuldzinsen"; Anlagen-Darlehen wären Z56
    "software_hosting": 61,             # „übrige" (Alternative: Z51 laufende EDV-Kosten)
    "buerobedarf": 61,                  # „übrige" (Alternative: Z52 Arbeitsmittel)
    "kontogebuehren": 61,
    "geschenke": 63,
    "bewirtung": 64,
    "verpflegungsmehraufwand": 65,
    "arbeitszimmer": 66,
    "homeoffice_pauschale": 67,
    "kfz_kosten": 71,                   # Treibstoff/Reparatur; Leasing wäre Z69, Steuer/Vers. Z70
    "oepnv": 71,                        # „… Kosten für öffentliche Verkehrsmittel"
    "fahrtkosten_kfz": 72,
    "wege_wohnung_betrieb": 74,
}

ZEILEN_JE_JAHR: dict[int, list[tuple[int, str]]] = {2025: ZEILEN_2025, 2026: ZEILEN_2026}
MAPPING_JE_JAHR: dict[int, dict[str, int]] = {2025: MAPPING_2025, 2026: MAPPING_2026}

# jahr -> (vorlaeufig, quelle)
JAHRE: dict[int, tuple[int, str]] = {
    2025: (0, "BMF-Schreiben vom 29.08.2025 „Anlage EÜR 2025“ (Vordruck 2025AnlEÜR801–803)"),
    2026: (0, "BMF-Schreiben vom 01.09.2026 „Anlage EÜR 2026“ (Vordruck 2026AnlEÜR801–803, Anleitung 08/2026)"),
}


def _pruefe_stammdaten() -> None:
    """Konsistenz der Stammdaten (läuft bei jedem Start, schlägt früh und laut fehl)."""
    keys = {k[0] for k in KATEGORIEN}
    for jahr in JAHRE:
        mapping = MAPPING_JE_JAHR[jahr]
        zeilen = {nummer for nummer, _ in ZEILEN_JE_JAHR[jahr]}
        if set(mapping) != keys:
            raise ValueError(f"Mapping {jahr}: Kategorien passen nicht ({set(mapping) ^ keys}).")
        for key, nummer in mapping.items():
            # Defensiver Guard: kein Mapping darf auf eine nie befüllte Zeile zeigen.
            if nummer in nie_befuellt(jahr):
                raise ValueError(f"Mapping {jahr} {key} -> Zeile {nummer} ist nie befüllt (KU brutto).")
            if nummer not in zeilen:
                raise ValueError(f"Mapping {jahr} {key} -> Zeile {nummer} fehlt in den Zeilen-Stammdaten.")


def seed(conn: sqlite3.Connection) -> None:
    _pruefe_stammdaten()

    # 1) Kategorien (aktiv NICHT überschreiben, damit Deaktivierung erhalten bleibt)
    conn.executemany(
        """
        INSERT INTO kategorie (key, name, typ, abzug_quote, ist_afa, belegpflicht_extra, sort_order)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET
            name=excluded.name,
            typ=excluded.typ,
            abzug_quote=excluded.abzug_quote,
            ist_afa=excluded.ist_afa,
            belegpflicht_extra=excluded.belegpflicht_extra,
            sort_order=excluded.sort_order
        """,
        KATEGORIEN,
    )

    # key -> id
    key_to_id = {r["key"]: r["id"] for r in conn.execute("SELECT id, key FROM kategorie")}

    for jahr, (vorlaeufig, quelle) in JAHRE.items():
        zeilen = ZEILEN_JE_JAHR[jahr]
        mapping = MAPPING_JE_JAHR[jahr]
        # 2) Jahr-Meta
        conn.execute(
            """
            INSERT INTO euer_jahr (jahr, vorlaeufig, quelle) VALUES (?, ?, ?)
            ON CONFLICT(jahr) DO UPDATE SET vorlaeufig=excluded.vorlaeufig, quelle=excluded.quelle
            """,
            (jahr, vorlaeufig, quelle),
        )
        # 3) Zeilen
        conn.executemany(
            """
            INSERT INTO euer_zeile (jahr, nummer, bezeichnung, sort_order) VALUES (?, ?, ?, ?)
            ON CONFLICT(jahr, nummer) DO UPDATE SET
                bezeichnung=excluded.bezeichnung, sort_order=excluded.sort_order
            """,
            [(jahr, nummer, bez, nummer) for nummer, bez in zeilen],
        )
        # 4) Mapping
        conn.executemany(
            """
            INSERT INTO euer_mapping (jahr, kategorie_id, zeile_nummer) VALUES (?, ?, ?)
            ON CONFLICT(jahr, kategorie_id) DO UPDATE SET zeile_nummer=excluded.zeile_nummer
            """,
            [(jahr, key_to_id[key], nummer) for key, nummer in mapping.items()],
        )
        # 5) Veraltete Zeilen entfernen (z. B. die frühere 2026-Kopie von 2025) — das
        #    Mapping zeigt jetzt nur noch auf die aktuellen Zeilen, keine FK-Abhängigkeit.
        nummern = [nummer for nummer, _ in zeilen]
        conn.execute(
            f"DELETE FROM euer_zeile WHERE jahr = ? AND nummer NOT IN ({','.join('?' * len(nummern))})",
            (jahr, *nummern),
        )

    conn.commit()
