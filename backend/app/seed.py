"""Idempotenter Stammdaten-Seed (Upsert) — Quelle: EUER_KATEGORIEN.md (VZ 2025).

Stammdaten (kategorie, euer_jahr, euer_zeile, euer_mapping) werden per
ON CONFLICT DO UPDATE geseedet, damit Mapping-Korrekturen einfach deploybar sind.
Nutzerdaten (gewerbe, buchung, afa_buchung) werden NICHT angefasst.

Mapping ist jahres-versioniert: 2025 (verifiziert) und 2026 (vorläufige Kopie,
Vordruck 2026 noch nicht erschienen).

Nie befüllte Zeilen (Kleinunternehmer = brutto): 15, 17, 57, 58.
"""
from __future__ import annotations

import sqlite3

# Zeilen, die bei Kleinunternehmern niemals befüllt werden (Guard im Export).
NIE_BEFUELLT: set[int] = {15, 17, 57, 58}

# (key, name, typ, abzug_quote, ist_afa, belegpflicht_extra, sort_order)
KATEGORIEN: list[tuple] = [
    # --- Einnahmen ---
    ("einnahme_ku",        "Einnahme Kleinunternehmer (z. B. App-/IAP-Erlöse)", "einnahme", 1.0, 0, 0, 10),
    ("einnahme_steuerfrei","Umsatzsteuerfreie Einnahme §4 Nr. 11 (Courtage)",   "einnahme", 1.0, 0, 0, 11),
    ("veraeusserung_av",   "Veräußerung/Entnahme Anlagevermögen",               "einnahme", 1.0, 0, 0, 12),
    ("kfz_privatnutzung",  "Private Kfz-Nutzung (1 %-Regelung, Betriebs-Kfz)",  "einnahme", 1.0, 0, 0, 13),
    # --- Ausgaben: Wareneinsatz/Fremdleistungen ---
    ("waren",              "Waren / Roh- und Hilfsstoffe",                       "ausgabe", 1.0, 0, 0, 20),
    ("fremdleistungen",    "Bezogene Leistungen / Fremdleistungen / Provisionen","ausgabe", 1.0, 0, 0, 21),
    # --- Ausgaben: AfA / GWG ---
    ("afa_beweglich",      "AfA bewegliche Wirtschaftsgüter (Hardware > 800 €)", "ausgabe", 1.0, 1, 0, 22),
    ("gwg",                "GWG-Sofortabzug (≤ 800 € netto)",                    "ausgabe", 1.0, 0, 0, 23),
    ("restbuchwert",       "Restbuchwert ausgeschiedener Anlagegüter",           "ausgabe", 1.0, 0, 0, 24),
    # --- Ausgaben: Raumkosten ---
    ("miete_raeume",       "Miete betrieblich genutzte Räume",                   "ausgabe", 1.0, 0, 0, 25),
    ("grundstueck_sonstige","Sonstige Grundstücksaufwendungen (betrieblich)",    "ausgabe", 1.0, 0, 0, 26),
    # --- Ausgaben: sonstige unbeschränkt abziehbar (Default Zeile 60, ⚠ Vordruck-Abgleich) ---
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
]

# (nummer, bezeichnung) — Zeilen-Stammdaten (Basis, gilt für 2025 und vorläufig 2026)
ZEILEN: list[tuple[int, str]] = [
    (12, "Betriebseinnahmen als umsatzsteuerlicher Kleinunternehmer (brutto)"),
    (16, "Umsatzsteuerfreie Betriebseinnahmen (§4 UStG)"),
    (19, "Veräußerung/Entnahme von Anlagevermögen"),
    (20, "Private Kfz-Nutzung / Nutzungsentnahmen (1 %-Regelung)"),
    (27, "Waren, Roh- und Hilfsstoffe"),
    (29, "Bezogene Leistungen / Fremdleistungen"),
    (33, "Abschreibungen auf bewegliche Wirtschaftsgüter (AfA)"),
    (36, "Sofortabschreibung geringwertiger Wirtschaftsgüter (GWG)"),
    (38, "Restbuchwert ausgeschiedener Anlagegüter"),
    (40, "Miete/Aufwendungen für betrieblich genutzte Räume"),
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
MAPPING: dict[str, int] = {
    "einnahme_ku": 12,
    "einnahme_steuerfrei": 16,
    "veraeusserung_av": 19,
    "kfz_privatnutzung": 20,            # ⚠ Vordruck-Abgleich (lt. EUER_KATEGORIEN.md §4.6)
    "waren": 27,
    "fremdleistungen": 29,
    "afa_beweglich": 33,
    "gwg": 36,
    "restbuchwert": 38,
    "miete_raeume": 40,
    "grundstueck_sonstige": 41,
    "reise_nebenkosten": 44,
    "software_hosting": 60,
    "buerobedarf": 60,
    "telekommunikation": 60,            # ⚠ Vordruck-Abgleich (Default 60, gewinnneutral)
    "versicherungen_betrieb": 60,       # ⚠
    "miete_leasing_bwg": 60,            # ⚠
    "wartung_reparatur": 60,            # ⚠
    "rechts_steuer_buchfuehrung": 60,   # ⚠
    "fortbildung": 60,                  # ⚠
    "werbung_repraesentation": 60,      # ⚠
    "kontogebuehren": 60,               # ✅ „übrige" (wie buerobedarf/software)
    "kfz_kosten": 60,                   # ⚠ final Zeile 68–70 (Kfz-Block) beim Vordruck-Abgleich
    "oepnv": 60,                        # ⚠ final Zeile 70 (sonstige tatsächliche Fahrtkosten)
    "geschenke": 62,
    "bewirtung": 63,
    "verpflegungsmehraufwand": 64,
    "arbeitszimmer": 65,
    "homeoffice_pauschale": 66,
    "fahrtkosten_kfz": 71,
    "wege_wohnung_betrieb": 73,
}

# jahr -> (vorlaeufig, quelle)
JAHRE: dict[int, tuple[int, str]] = {
    2025: (0, "ELSTER „Anleitung zur EÜR 2025“ (Stand 08/2025), Anlage EÜR 1.9.1.1"),
    2026: (1, "Vorläufig: Kopie von 2025 — Vordruck 2026 noch nicht erschienen, vor Steuersaison abgleichen"),
}


def seed(conn: sqlite3.Connection) -> None:
    # Defensiver Guard: kein Mapping darf auf eine nie befüllte Zeile zeigen.
    for key, nummer in MAPPING.items():
        if nummer in NIE_BEFUELLT:
            raise ValueError(f"Mapping {key} -> Zeile {nummer} ist eine nie befüllte Zeile (KU brutto).")

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
            [(jahr, nummer, bez, nummer) for nummer, bez in ZEILEN],
        )
        # 4) Mapping
        conn.executemany(
            """
            INSERT INTO euer_mapping (jahr, kategorie_id, zeile_nummer) VALUES (?, ?, ?)
            ON CONFLICT(jahr, kategorie_id) DO UPDATE SET zeile_nummer=excluded.zeile_nummer
            """,
            [(jahr, key_to_id[key], nummer) for key, nummer in MAPPING.items()],
        )

    conn.commit()
