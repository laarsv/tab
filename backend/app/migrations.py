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
    Migration(
        version=3,
        sql="""
        -- v3: Belege als EINGANG (erst hochladen, später zuordnen) +
        --     Buchung als Beleg-Kopf mit mehreren POSITIONEN (Kategorie-Splits).

        -- 1) Positionen-Tabelle + bestehende Buchungszeilen übernehmen
        CREATE TABLE buchung_position (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            buchung_id    INTEGER NOT NULL REFERENCES buchung(id) ON DELETE CASCADE,
            kategorie_id  INTEGER NOT NULL REFERENCES kategorie(id),
            betrag_cent   INTEGER NOT NULL,
            beleg_details TEXT
        );
        INSERT INTO buchung_position (buchung_id, kategorie_id, betrag_cent, beleg_details)
            SELECT id, kategorie_id, betrag_cent, beleg_details FROM buchung;
        CREATE INDEX idx_position_buchung ON buchung_position(buchung_id);

        -- 2) buchung -> reiner Kopf (ohne kategorie_id/betrag_cent/beleg_details)
        CREATE TABLE buchung_new (
            id           INTEGER PRIMARY KEY,
            gewerbe_id   INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            datum        TEXT    NOT NULL,
            beschreibung TEXT,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO buchung_new (id, gewerbe_id, datum, beschreibung, created_at, updated_at)
            SELECT id, gewerbe_id, datum, beschreibung, created_at, updated_at FROM buchung;
        DROP TABLE buchung;
        ALTER TABLE buchung_new RENAME TO buchung;
        CREATE INDEX idx_buchung_gewerbe_datum ON buchung(gewerbe_id, datum);

        -- 3) beleg -> Eingang: gewerbe_id NOT NULL, buchung_id NULLABLE (NULL = offen/Eingang),
        --    beim Löschen einer Buchung fallen Belege zurück in den Eingang (SET NULL)
        CREATE TABLE beleg_new (
            id            INTEGER PRIMARY KEY,
            gewerbe_id    INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            buchung_id    INTEGER REFERENCES buchung(id) ON DELETE SET NULL,
            original_name TEXT    NOT NULL,
            stored_name   TEXT    NOT NULL,
            content_type  TEXT    NOT NULL,
            size_bytes    INTEGER NOT NULL,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO beleg_new
            (id, gewerbe_id, buchung_id, original_name, stored_name, content_type, size_bytes, created_at)
            SELECT b.id,
                   (SELECT gewerbe_id FROM buchung WHERE buchung.id = b.buchung_id),
                   b.buchung_id, b.original_name, b.stored_name, b.content_type, b.size_bytes, b.created_at
            FROM beleg b;
        DROP TABLE beleg;
        ALTER TABLE beleg_new RENAME TO beleg;
        CREATE INDEX idx_beleg_buchung ON beleg(buchung_id);
        CREATE INDEX idx_beleg_gewerbe ON beleg(gewerbe_id);
        """,
    ),
    Migration(
        version=4,
        sql="""
        -- v4: Abgang (Verkauf/Entnahme/Verschrottung) eines AfA-Wirtschaftsguts.
        --     AfA endet mit dem Abgangsmonat; Restbuchwert wird berechnet, nicht gespeichert.
        ALTER TABLE afa_buchung ADD COLUMN abgang_datum TEXT;
        """,
    ),
    Migration(
        version=5,
        sql="""
        -- v5: Fahrten-Liste für die km-Pauschale (Privatwagen, Zeile 71).
        --     KEIN Fahrtenbuch i. S. d. 1 %-Alternative — nur Nachweis-Liste
        --     („glaubhaft machen"): Datum, Ziel, Anlass, km.
        CREATE TABLE fahrt (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id  INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            datum       TEXT    NOT NULL,
            ziel        TEXT    NOT NULL,
            anlass      TEXT,
            km          REAL    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_fahrt_gewerbe_datum ON fahrt(gewerbe_id, datum);
        """,
    ),
    Migration(
        version=6,
        sql="""
        -- v6: Rechnungsmodul (KU-Rechnungen mit §19-Hinweis, PDF + Mail-Versand) +
        --     Absender-Stammdaten am Gewerbe + individuelle Mail-Einstellungen je Login.

        ALTER TABLE gewerbe ADD COLUMN anschrift TEXT;           -- Absender (Name + Adresse, mehrzeilig)
        ALTER TABLE gewerbe ADD COLUMN iban TEXT;
        ALTER TABLE gewerbe ADD COLUMN rechnung_fusszeile TEXT;  -- z. B. Bankname, Zahlungsziel

        CREATE TABLE rechnung (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id           INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            jahr                 INTEGER NOT NULL,
            laufnummer           INTEGER NOT NULL,
            nummer               TEXT    NOT NULL,               -- z. B. 2026-0007
            datum                TEXT    NOT NULL,
            leistungsdatum       TEXT,                            -- frei, z. B. "03/2026"
            empfaenger_name      TEXT    NOT NULL,
            empfaenger_anschrift TEXT,
            empfaenger_email     TEXT,
            notiz                TEXT,
            status               TEXT    NOT NULL DEFAULT 'entwurf'
                                 CHECK (status IN ('entwurf','versendet','bezahlt','storniert')),
            versendet_am         TEXT,
            bezahlt_am           TEXT,
            created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at           TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (gewerbe_id, jahr, laufnummer)
        );
        CREATE TABLE rechnung_position (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            rechnung_id      INTEGER NOT NULL REFERENCES rechnung(id) ON DELETE CASCADE,
            beschreibung     TEXT    NOT NULL,
            menge            REAL    NOT NULL DEFAULT 1,
            einzelpreis_cent INTEGER NOT NULL
        );
        CREATE INDEX idx_rechnung_gewerbe ON rechnung(gewerbe_id, jahr);
        CREATE INDEX idx_rechnung_position ON rechnung_position(rechnung_id);

        -- Gmail-App-Passwort je Login-E-Mail (Fernet-verschlüsselt, nie im Klartext).
        CREATE TABLE user_mail (
            email             TEXT PRIMARY KEY,
            app_passwort_enc  TEXT NOT NULL,
            updated_at        TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
    ),
    Migration(
        version=7,
        sql="""
        -- v7: Steuer-Hinweis je Rechnung wählbar: 'ku19' (§19 Kleinunternehmer, Default)
        --     oder 'vers4nr11' (steuerfreie Versicherungsvermittlung §4 Nr. 11 UStG).
        ALTER TABLE rechnung ADD COLUMN steuerhinweis TEXT NOT NULL DEFAULT 'ku19';
        """,
    ),
    Migration(
        version=8,
        sql="""
        -- v8: Wiederkehrende Rechnungen (Abos). Vorlage inkl. Positionen (JSON);
        --     der Scheduler erstellt zum Stichtag eine echte Rechnung und versendet
        --     sie optional automatisch vom hinterlegten Absender (user_mail).
        CREATE TABLE rechnung_abo (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id           INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            empfaenger_name      TEXT    NOT NULL,
            empfaenger_anschrift TEXT,
            empfaenger_email     TEXT,
            notiz                TEXT,
            steuerhinweis        TEXT    NOT NULL DEFAULT 'ku19',
            positionen_json      TEXT    NOT NULL,
            intervall            TEXT    NOT NULL
                                 CHECK (intervall IN ('monatlich','vierteljaehrlich','jaehrlich')),
            naechste_am          TEXT    NOT NULL,
            auto_senden          INTEGER NOT NULL DEFAULT 0,
            betreff              TEXT,
            mail_text            TEXT,
            absender_email       TEXT    NOT NULL,
            aktiv                INTEGER NOT NULL DEFAULT 1,
            created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at           TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_abo_gewerbe ON rechnung_abo(gewerbe_id);
        CREATE INDEX idx_abo_faellig ON rechnung_abo(aktiv, naechste_am);
        """,
    ),
    Migration(
        version=9,
        sql="""
        -- v9: Kontakte (Rechnungsempfänger). Füllen sich automatisch: jede erstellte
        --     Rechnung upsertet ihren Empfänger (Name case-insensitiv eindeutig je Gewerbe).
        CREATE TABLE kontakt (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id  INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL COLLATE NOCASE,
            anschrift   TEXT,
            email       TEXT,
            notiz       TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (gewerbe_id, name)
        );
        -- Backfill aus bestehenden Rechnungen.
        INSERT INTO kontakt (gewerbe_id, name, anschrift, email)
            SELECT gewerbe_id, empfaenger_name,
                   MAX(empfaenger_anschrift), MAX(empfaenger_email)
            FROM rechnung
            GROUP BY gewerbe_id, empfaenger_name COLLATE NOCASE;
        """,
    ),
    Migration(
        version=10,
        sql="""
        -- v10: optionales Fälligkeitsdatum am Eingangs-Beleg — macht den Eingang
        --      nebenbei zur „noch zu zahlen"-Liste (kein Banking, nur Erinnerung).
        ALTER TABLE beleg ADD COLUMN faellig_am TEXT;
        """,
    ),
    Migration(
        version=11,
        sql="""
        -- v11: Beleg-Eingang per E-Mail (IMAP-Abruf der eigenen +tab-Adresse) —
        --      Einstellungen je Login + Dedup-Log über Message-IDs.
        ALTER TABLE user_mail ADD COLUMN import_aktiv INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE user_mail ADD COLUMN import_gewerbe_id INTEGER
            REFERENCES gewerbe(id) ON DELETE SET NULL;
        CREATE TABLE mail_import (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            email       TEXT NOT NULL,
            message_id  TEXT NOT NULL,
            beleg_ids   TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE (email, message_id)
        );
        """,
    ),
    Migration(
        version=12,
        sql="""
        -- v12: Mandantentrennung — jedes Gewerbe gehört einem Login (owner_email).
        --      NULL = Alt-Bestand (für alle sichtbar, bis manuell zugeordnet);
        --      Durchsetzung in JEDER Route via auth/deps.check_gewerbe.
        ALTER TABLE gewerbe ADD COLUMN owner_email TEXT;
        """,
    ),
    Migration(
        version=13,
        sql="""
        -- v13: Eigener Mail-Server je Login (Option B): provider 'google' (Default,
        --      smtp/imap.gmail.com) oder 'custom' (beliebiger Anbieter, z. B. All-Inkl).
        --      absender_email = From: auf Rechnungen; import_adresse = Ziel für den
        --      Beleg-Mail-Import (Fallback: +tab-Variante des Absenders).
        ALTER TABLE user_mail ADD COLUMN provider TEXT NOT NULL DEFAULT 'google';
        ALTER TABLE user_mail ADD COLUMN smtp_host TEXT;
        ALTER TABLE user_mail ADD COLUMN smtp_port INTEGER;
        ALTER TABLE user_mail ADD COLUMN imap_host TEXT;
        ALTER TABLE user_mail ADD COLUMN imap_port INTEGER;
        ALTER TABLE user_mail ADD COLUMN mail_benutzer TEXT;
        ALTER TABLE user_mail ADD COLUMN absender_email TEXT;
        ALTER TABLE user_mail ADD COLUMN import_adresse TEXT;
        """,
    ),
]


def run_migrations(conn: sqlite3.Connection) -> int:
    """Wendet ausstehende Migrationen an. Gibt die neue Schema-Version zurück.

    Foreign-Keys werden während der Migration deaktiviert (für Tabellen-Rebuilds nötig)
    und danach wieder aktiviert — Standardvorgehen bei SQLite-Schemaänderungen.
    """
    current = conn.execute("PRAGMA user_version;").fetchone()[0]
    pending = [m for m in sorted(MIGRATIONS, key=lambda m: m.version) if m.version > current]
    if not pending:
        return current

    conn.execute("PRAGMA foreign_keys = OFF;")
    applied = current
    try:
        for mig in pending:
            conn.executescript("BEGIN;\n" + mig.sql + "\nCOMMIT;")
            conn.execute(f"PRAGMA user_version = {mig.version};")
            applied = mig.version
    finally:
        conn.execute("PRAGMA foreign_keys = ON;")
    return applied
