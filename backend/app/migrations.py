"""Simple Migrations-Liste (ITA-Stil) — keine Alembic.

Jede Migration = (version, SQL). Beim Start werden alle Migrationen mit
version > PRAGMA user_version in einer Transaktion angewandt und user_version
hochgesetzt. Stammdaten-Seed läuft separat (seed.py) und ist idempotent (Upsert),
damit Mapping-Korrekturen deploybar sind.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Migration:
    version: int
    sql: str


MIGRATIONS: list[Migration] = [
    Migration(
        version=1,
        sql="""
        CREATE TABLE gewerbe (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT    NOT NULL,
            steuernummer  TEXT,
            aktiv         INTEGER NOT NULL DEFAULT 1,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE kategorie (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            key                 TEXT    NOT NULL UNIQUE,
            name                TEXT    NOT NULL,
            typ                 TEXT    NOT NULL CHECK (typ IN ('einnahme','ausgabe')),
            abzug_quote         REAL    NOT NULL DEFAULT 1.0,
            ist_afa             INTEGER NOT NULL DEFAULT 0,
            belegpflicht_extra  INTEGER NOT NULL DEFAULT 0,
            sort_order          INTEGER NOT NULL DEFAULT 0,
            aktiv               INTEGER NOT NULL DEFAULT 1
        );

        -- Versionierungs-Meta pro Veranlagungszeitraum (VZ).
        CREATE TABLE euer_jahr (
            jahr        INTEGER PRIMARY KEY,
            vorlaeufig  INTEGER NOT NULL DEFAULT 0,
            quelle      TEXT
        );

        -- Zeilen-Stammdaten je VZ (jahres-versioniert).
        CREATE TABLE euer_zeile (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            jahr         INTEGER NOT NULL,
            nummer       INTEGER NOT NULL,
            bezeichnung  TEXT    NOT NULL,
            sort_order   INTEGER NOT NULL DEFAULT 0,
            UNIQUE (jahr, nummer)
        );

        -- Kategorie -> Zeile je VZ (Kern der Versionierung).
        CREATE TABLE euer_mapping (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            jahr          INTEGER NOT NULL,
            kategorie_id  INTEGER NOT NULL REFERENCES kategorie(id) ON DELETE CASCADE,
            zeile_nummer  INTEGER NOT NULL,
            UNIQUE (jahr, kategorie_id)
        );

        -- Normale Buchungen (Einnahmen/Ausgaben inkl. GWG, Bewirtung). AfA separat.
        CREATE TABLE buchung (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id     INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            datum          TEXT    NOT NULL,               -- Zahlungsdatum YYYY-MM-DD
            betrag_cent    INTEGER NOT NULL,               -- brutto, positiv
            kategorie_id   INTEGER NOT NULL REFERENCES kategorie(id),
            beschreibung   TEXT,
            beleg_details  TEXT,                            -- Pflicht bei belegpflicht_extra
            created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_buchung_gewerbe_datum ON buchung(gewerbe_id, datum);

        -- AfA-Wirtschaftsgüter (Jahres-AfA wird berechnet, nicht gespeichert).
        CREATE TABLE afa_buchung (
            id                       INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id               INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            kategorie_id             INTEGER NOT NULL REFERENCES kategorie(id),
            bezeichnung              TEXT    NOT NULL,
            anschaffungskosten_cent  INTEGER NOT NULL,
            anschaffungsdatum        TEXT    NOT NULL,      -- YYYY-MM-DD
            nutzungsdauer_jahre      INTEGER NOT NULL,
            afa_methode              TEXT    NOT NULL DEFAULT 'linear',
            beschreibung             TEXT,
            created_at               TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at               TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_afa_gewerbe ON afa_buchung(gewerbe_id);
        """,
    ),
    Migration(
        version=2,
        sql="""
        -- Besteuerungsart je Gewerbe: 'kleinunternehmer' (§19) oder 'regelbesteuerung'.
        -- Fundament für expliziten KU-Status + spätere Regelbesteuerung.
        ALTER TABLE gewerbe ADD COLUMN besteuerung TEXT NOT NULL DEFAULT 'kleinunternehmer';

        -- Beleg-Dateien (PDF/Bild) je Buchung.
        CREATE TABLE beleg (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            buchung_id     INTEGER NOT NULL REFERENCES buchung(id) ON DELETE CASCADE,
            original_name  TEXT    NOT NULL,
            stored_name    TEXT    NOT NULL,
            content_type   TEXT    NOT NULL,
            size_bytes     INTEGER NOT NULL,
            created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_beleg_buchung ON beleg(buchung_id);
        """,
    ),
]


def run_migrations(conn: sqlite3.Connection) -> int:
    """Wendet ausstehende Migrationen an. Gibt die neue Schema-Version zurück."""
    current = conn.execute("PRAGMA user_version;").fetchone()[0]
    applied = current
    for mig in sorted(MIGRATIONS, key=lambda m: m.version):
        if mig.version <= current:
            continue
        conn.executescript("BEGIN;\n" + mig.sql + "\nCOMMIT;")
        conn.execute(f"PRAGMA user_version = {mig.version};")
        applied = mig.version
    return applied
