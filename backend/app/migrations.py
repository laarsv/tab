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
    Migration(
        version=14,
        sql="""
        -- v14: Anmeldung ohne Google — E-Mail + Passwort (scrypt), Verifizierung
        --      und Passwort-Reset per Code (System-Mail-Absender, SYSTEM_SMTP_*).
        CREATE TABLE nutzer (
            email              TEXT PRIMARY KEY,
            passwort_hash      TEXT NOT NULL,
            name               TEXT,
            verifiziert        INTEGER NOT NULL DEFAULT 0,
            verify_code        TEXT,
            verify_gueltig_bis TEXT,
            reset_code         TEXT,
            reset_gueltig_bis  TEXT,
            created_at         TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at         TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """,
    ),
    Migration(
        version=15,
        sql="""
        -- v15: Rechnung → Einnahme-Buchung verknüpfen, damit „Als Einnahme buchen" nach dem
        --      Verbuchen verschwindet (und nach Löschen der Buchung wieder erscheint).
        ALTER TABLE rechnung ADD COLUMN buchung_id INTEGER REFERENCES buchung(id) ON DELETE SET NULL;

        -- Bestand: bisher vorbefüllte Buchungen heißen „Rechnung {nummer} – {Empfänger}".
        UPDATE rechnung SET buchung_id = (
            SELECT b.id FROM buchung b
            WHERE b.gewerbe_id = rechnung.gewerbe_id
              AND (b.beschreibung = 'Rechnung ' || rechnung.nummer
                   OR b.beschreibung LIKE 'Rechnung ' || rechnung.nummer || ' %')
            ORDER BY b.id LIMIT 1
        );
        """,
    ),
    Migration(
        version=16,
        sql="""
        -- v16: „Neuigkeiten gelesen" je Account statt je Browser (localStorage ging bei
        --      anderem Gerät/Browser/PWA/Storage-Reset verloren → Fenster kam immer wieder).
        CREATE TABLE news_gelesen (
            email       TEXT    NOT NULL,
            news_id     INTEGER NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (email, news_id)
        );
        """,
    ),
    Migration(
        version=17,
        sql="""
        -- v17: Fälligkeit + Mahnwesen.
        --  * rechnung.zahlungsziel_tage / faellig_am: NULL = Bestand ohne vereinbartes Ziel
        --    (die Überfällig-Logik nimmt dann Rechnungsdatum + 30 Tage, § 286 Abs. 3 BGB).
        --  * gewerbe: Standard-Zahlungsziel, Mahnfrist, Mahngebühr je Stufe, Basiszinssatz
        --    (Basispunkte; NULL = keine Verzugszinsen).
        --  * mahnung: unveränderlicher Schnappschuss je erstelltem Schreiben (Stufe 1-3).
        ALTER TABLE gewerbe ADD COLUMN zahlungsziel_tage INTEGER NOT NULL DEFAULT 14;
        ALTER TABLE gewerbe ADD COLUMN mahn_frist_tage INTEGER NOT NULL DEFAULT 10;
        ALTER TABLE gewerbe ADD COLUMN mahn_gebuehr_1_cent INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE gewerbe ADD COLUMN mahn_gebuehr_2_cent INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE gewerbe ADD COLUMN mahn_gebuehr_3_cent INTEGER NOT NULL DEFAULT 0;
        ALTER TABLE gewerbe ADD COLUMN basiszinssatz_bp INTEGER;

        ALTER TABLE rechnung ADD COLUMN zahlungsziel_tage INTEGER;
        ALTER TABLE rechnung ADD COLUMN faellig_am TEXT;

        CREATE TABLE mahnung (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            rechnung_id    INTEGER NOT NULL REFERENCES rechnung(id) ON DELETE CASCADE,
            stufe          INTEGER NOT NULL CHECK (stufe IN (1, 2, 3)),
            datum          TEXT    NOT NULL,
            frist_am       TEXT    NOT NULL,
            offen_cent     INTEGER NOT NULL,
            gebuehr_cent   INTEGER NOT NULL DEFAULT 0,
            pauschale_cent INTEGER NOT NULL DEFAULT 0,
            zinsen_cent    INTEGER NOT NULL DEFAULT 0,
            zinssatz_bp    INTEGER NOT NULL DEFAULT 0,
            zinstage       INTEGER NOT NULL DEFAULT 0,
            gesamt_cent    INTEGER NOT NULL,
            einleitung     TEXT    NOT NULL,
            schluss        TEXT,
            gesendet_am    TEXT,
            created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_mahnung_rechnung ON mahnung(rechnung_id);
        """,
    ),
    Migration(
        version=18,
        sql="""
        -- v18: Kontoinhaber für den GiroCode (EPC-QR) und die E-Rechnung (BT-85). Banken prüfen
        --      beim Überweisen, ob der Empfängername zum Konto passt (Empfängerüberprüfung).
        --      NULL = erste Zeile der Rechnungs-Anschrift.
        ALTER TABLE gewerbe ADD COLUMN kontoinhaber TEXT;
        """,
    ),
    Migration(
        version=19,
        sql="""
        -- v19: Fristen-Seite. Einstellungen je Login (Kalender-Abo + ESt-Vorauszahlungen anzeigen)
        --      und manuell erledigte Fristen. Vom Kalender-Link wird nur der SHA-256-Hash
        --      gespeichert — der Link selbst ist nur beim Erzeugen sichtbar.
        CREATE TABLE frist_einstellung (
            email               TEXT PRIMARY KEY,
            kalender_token_hash TEXT,
            kalender_seit       TEXT,
            est_vorauszahlung   INTEGER NOT NULL DEFAULT 0,
            updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_frist_token ON frist_einstellung(kalender_token_hash);
        CREATE TABLE frist_erledigt (
            email       TEXT NOT NULL,
            schluessel  TEXT NOT NULL,
            erledigt_am TEXT NOT NULL,
            PRIMARY KEY (email, schluessel)
        );
        """,
    ),
    Migration(
        version=20,
        sql="""
        -- v20: Festschreibung. Die Trigger (Sperren, Änderungsprotokoll, Hash-Kette) legt
        --      services/audit.ensure_triggers() bei jedem Start an und hält sie aktuell —
        --      hier nur die Tabellen.
        --  * audit_log: Änderungsprotokoll, nur anhängbar. row_hash = SHA-256 über
        --    prev_hash + Inhalt (Hash-Kette, wird von Triggern gesetzt).
        --  * jahr_abschluss: je Gewerbe + Jahr. abgeschlossen = 1 sperrt Buchungen, Belege,
        --    Fahrten und AfA des Jahres; siegel = SHA-256 über die Daten beim Abschluss.
        CREATE TABLE audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          TEXT    NOT NULL,
            actor       TEXT,
            gewerbe_id  INTEGER,
            tabelle     TEXT    NOT NULL,
            zeile_id    INTEGER NOT NULL,
            aktion      TEXT    NOT NULL,
            vorher      TEXT,
            nachher     TEXT,
            prev_hash   TEXT,
            row_hash    TEXT
        );
        CREATE INDEX idx_audit_gewerbe ON audit_log(gewerbe_id, id);
        CREATE INDEX idx_audit_zeile ON audit_log(tabelle, zeile_id);

        CREATE TABLE jahr_abschluss (
            gewerbe_id         INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            jahr               INTEGER NOT NULL,
            abgeschlossen      INTEGER NOT NULL DEFAULT 1,
            abgeschlossen_am   TEXT,
            abgeschlossen_von  TEXT,
            siegel             TEXT,
            siegel_info        TEXT,
            geoeffnet_am       TEXT,
            geoeffnet_von      TEXT,
            geoeffnet_grund    TEXT,
            PRIMARY KEY (gewerbe_id, jahr)
        );
        """,
    ),
    Migration(
        version=21,
        sql="""
        -- v21: Bank-Import (Kontoauszug als CAMT.053 oder CSV, KEIN Bankabruf). Jeder Umsatz
        --      wird einer Buchung zugeordnet (buchung_id), ignoriert (privat/Umbuchung) oder
        --      bleibt offen. Zugeordnet = buchung_id IS NOT NULL — wird die Buchung gelöscht,
        --      ist der Umsatz automatisch wieder offen (ON DELETE SET NULL).
        CREATE TABLE bankkonto (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id  INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL,
            iban        TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (gewerbe_id, iban)
        );
        CREATE TABLE bank_import (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            konto_id         INTEGER NOT NULL REFERENCES bankkonto(id) ON DELETE CASCADE,
            gewerbe_id       INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            dateiname        TEXT,
            sha256           TEXT    NOT NULL,
            format           TEXT    NOT NULL,
            von              TEXT,
            bis              TEXT,
            anzahl_neu       INTEGER NOT NULL DEFAULT 0,
            anzahl_dubletten INTEGER NOT NULL DEFAULT 0,
            saldo_pruefung   TEXT,
            importiert_am    TEXT    NOT NULL,
            importiert_von   TEXT
        );
        CREATE INDEX idx_bank_import_konto ON bank_import(konto_id);
        CREATE TABLE bank_umsatz (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            konto_id         INTEGER NOT NULL REFERENCES bankkonto(id) ON DELETE CASCADE,
            gewerbe_id       INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            import_id        INTEGER REFERENCES bank_import(id) ON DELETE SET NULL,
            datum            TEXT    NOT NULL,
            wert_datum       TEXT,
            betrag_cent      INTEGER NOT NULL,      -- mit Vorzeichen: + Eingang, - Ausgang
            gegenpartei      TEXT,
            gegenpartei_iban TEXT,
            verwendungszweck TEXT,
            referenz         TEXT,
            fingerprint      TEXT    NOT NULL,
            status           TEXT    NOT NULL DEFAULT 'offen' CHECK (status IN ('offen', 'ignoriert')),
            ignoriert_grund  TEXT,
            buchung_id       INTEGER REFERENCES buchung(id) ON DELETE SET NULL,
            zugeordnet_am    TEXT,
            created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (konto_id, fingerprint)
        );
        CREATE INDEX idx_umsatz_konto_datum ON bank_umsatz(konto_id, datum);
        CREATE INDEX idx_umsatz_buchung ON bank_umsatz(buchung_id);
        """,
    ),
    Migration(
        version=22,
        sql="""
        -- v22: Teilzahlungen, Skonto, Ausbuchen. Jede Zahlung auf eine Rechnung ist eine Zeile:
        --  art 'zahlung' = Geld eingegangen (optional mit Einnahme-Buchung, buchung_id),
        --  art 'skonto'  = Abzug des Kunden bei früher Zahlung (kein Einkommen, keine Buchung),
        --  art 'ausfall' = ausgebuchter Rest (Forderungsausfall; in der EÜR nie zugeflossen).
        --  Offen = Summe - Zahlungen - Ausbuchungen; bezahlt, sobald nichts mehr offen ist.
        ALTER TABLE rechnung ADD COLUMN skonto_bp INTEGER;      -- Skonto in Basispunkten (200 = 2,00 %)
        ALTER TABLE rechnung ADD COLUMN skonto_tage INTEGER;    -- Frist ab Rechnungsdatum

        CREATE TABLE rechnung_zahlung (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            rechnung_id    INTEGER NOT NULL REFERENCES rechnung(id) ON DELETE CASCADE,
            gewerbe_id     INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            datum          TEXT    NOT NULL,
            betrag_cent    INTEGER NOT NULL CHECK (betrag_cent > 0),
            art            TEXT    NOT NULL CHECK (art IN ('zahlung', 'skonto', 'ausfall')),
            buchung_id     INTEGER REFERENCES buchung(id) ON DELETE SET NULL,
            bank_umsatz_id INTEGER REFERENCES bank_umsatz(id) ON DELETE SET NULL,
            notiz          TEXT,
            created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_rz_rechnung ON rechnung_zahlung(rechnung_id);

        -- Bestand: bereits bezahlte Rechnungen bekommen eine Zahlung über die Summe (mit ihrer
        -- Einnahme-Buchung, falls gebucht) — so gilt überall dasselbe Modell.
        INSERT INTO rechnung_zahlung (rechnung_id, gewerbe_id, datum, betrag_cent, art, buchung_id)
            SELECT r.id, r.gewerbe_id, COALESCE(r.bezahlt_am, r.datum), s.summe, 'zahlung', r.buchung_id
            FROM rechnung r
            JOIN (SELECT rechnung_id, SUM(CAST(ROUND(menge * einzelpreis_cent) AS INTEGER)) AS summe
                  FROM rechnung_position GROUP BY rechnung_id) s ON s.rechnung_id = r.id
            WHERE r.status = 'bezahlt' AND s.summe > 0;
        """,
    ),
    Migration(
        version=23,
        sql="""
        -- v23: Angebote (eigener Nummernkreis AN-JJJJ-NNNN je Gewerbe + Jahr). Positionen sind normal
        --      oder optional (Zusatzleistung, zählt nicht zur Summe). Aus einem versendeten oder
        --      angenommenen Angebot entsteht per Klick ein Rechnungsentwurf (rechnung_id).
        CREATE TABLE angebot (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id           INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            jahr                 INTEGER NOT NULL,
            laufnummer           INTEGER NOT NULL,
            nummer               TEXT    NOT NULL,
            datum                TEXT    NOT NULL,
            gueltig_bis          TEXT    NOT NULL,
            empfaenger_name      TEXT    NOT NULL,
            empfaenger_anschrift TEXT,
            empfaenger_email     TEXT,
            einleitung           TEXT,
            notiz                TEXT,
            steuerhinweis        TEXT    NOT NULL DEFAULT 'ku19',
            status               TEXT    NOT NULL DEFAULT 'entwurf'
                                 CHECK (status IN ('entwurf', 'versendet', 'angenommen', 'abgelehnt')),
            versendet_am         TEXT,
            antwort_am           TEXT,
            rechnung_id          INTEGER REFERENCES rechnung(id) ON DELETE SET NULL,
            created_at           TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at           TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (gewerbe_id, jahr, laufnummer)
        );
        CREATE INDEX idx_angebot_gewerbe ON angebot(gewerbe_id, jahr);
        CREATE TABLE angebot_position (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            angebot_id       INTEGER NOT NULL REFERENCES angebot(id) ON DELETE CASCADE,
            beschreibung     TEXT    NOT NULL,
            menge            REAL    NOT NULL DEFAULT 1,
            einzelpreis_cent INTEGER NOT NULL,
            art              TEXT    NOT NULL DEFAULT 'normal' CHECK (art IN ('normal', 'optional'))
        );
        CREATE INDEX idx_angebot_position ON angebot_position(angebot_id);
        """,
    ),
    Migration(
        version=24,
        sql="""
        -- v24: Privatanteil + Dauerbelege.
        --  * buchung_position.privat_bp: privater Anteil in Basispunkten (0-10000, 2000 = 20 %). betrag_cent
        --    bleibt der gezahlte Betrag; nur der betriebliche Rest zählt in der EÜR (nur bei Ausgaben).
        --  * dauerbeleg: Vorlage für Ausgaben in festen Abständen (Miete, Versicherung, Abos). naechste_am ist
        --    der nächste noch offene Termin; anker_tag hält den Tag im Monat (31. -> Monatsende und zurück).
        --    Tab bucht nie von selbst: ein fälliger Termin wird mit einem Klick (oder über die Bank-Zuordnung)
        --    zur Buchung, dabei trägt die Buchung dauerbeleg_id + termin (je Termin höchstens eine Buchung).
        ALTER TABLE buchung_position ADD COLUMN privat_bp INTEGER NOT NULL DEFAULT 0
            CHECK (privat_bp BETWEEN 0 AND 10000);
        CREATE TABLE dauerbeleg (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id   INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            bezeichnung  TEXT    NOT NULL,
            notiz        TEXT,
            kategorie_id INTEGER NOT NULL REFERENCES kategorie(id),
            betrag_cent  INTEGER NOT NULL CHECK (betrag_cent > 0),
            privat_bp    INTEGER NOT NULL DEFAULT 0 CHECK (privat_bp BETWEEN 0 AND 10000),
            intervall    TEXT    NOT NULL
                         CHECK (intervall IN ('monatlich', 'vierteljaehrlich', 'halbjaehrlich', 'jaehrlich')),
            anker_tag    INTEGER NOT NULL CHECK (anker_tag BETWEEN 1 AND 31),
            naechste_am  TEXT    NOT NULL,
            endet_am     TEXT,
            aktiv        INTEGER NOT NULL DEFAULT 1,
            created_at   TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at   TEXT    NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_dauerbeleg_gewerbe ON dauerbeleg(gewerbe_id);
        ALTER TABLE buchung ADD COLUMN dauerbeleg_id INTEGER REFERENCES dauerbeleg(id) ON DELETE SET NULL;
        ALTER TABLE buchung ADD COLUMN termin TEXT;
        CREATE UNIQUE INDEX idx_buchung_dauerbeleg_termin ON buchung(dauerbeleg_id, termin)
            WHERE dauerbeleg_id IS NOT NULL;
        """,
    ),
    Migration(
        version=25,
        sql="""
        -- v25: AfA-Methoden. Die Methode steht in afa_methode (seit v1: 'linear', jetzt auch 'degressiv',
        --      'elektro', 'sammelposten'). degressiv_bp = Satz in Basispunkten (3000 = 30 %), linear_ab_jahr =
        --      freiwilliger früherer Wechsel zur linearen AfA. Bestehende Anlagen bleiben linear.
        ALTER TABLE afa_buchung ADD COLUMN degressiv_bp INTEGER;
        ALTER TABLE afa_buchung ADD COLUMN linear_ab_jahr INTEGER;
        """,
    ),
    Migration(
        version=26,
        sql="""
        -- v26: Rechnungs-Komfort. rechnung.bestellnummer = "Ihre Bestellnummer" (BT-13), gewerbe.logo_datei =
        --      Dateiname des Logos unter UPLOAD_ROOT/logos, artikel = Katalog häufiger Positionen (Preis brutto,
        --      Kleinunternehmer), textbaustein = wiederverwendbare Texte für Rechnungs- und Angebotstexte.
        ALTER TABLE rechnung ADD COLUMN bestellnummer TEXT;
        ALTER TABLE gewerbe ADD COLUMN logo_datei TEXT;
        CREATE TABLE artikel (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id  INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            bezeichnung TEXT    NOT NULL COLLATE NOCASE,
            preis_cent  INTEGER NOT NULL CHECK (preis_cent > 0),
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (gewerbe_id, bezeichnung)
        );
        CREATE TABLE textbaustein (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            gewerbe_id  INTEGER NOT NULL REFERENCES gewerbe(id) ON DELETE CASCADE,
            name        TEXT    NOT NULL COLLATE NOCASE,
            text        TEXT    NOT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE (gewerbe_id, name)
        );
        """,
    ),
    Migration(
        version=27,
        sql="""
        -- v27: Zugang für die Steuerberatung (nur lesen). berater_einladung = Einladungslink (nur der SHA-256-Hash
        --      des Tokens, einmal einlösbar, 72 h); berater_zugang = das Konto der Steuerberatung (eigene E-Mail +
        --      Passwort-Hash, unabhängig von Google/nutzer), gebunden an die Daten von owner_email. gesperrt = 1
        --      beendet den Zugang sofort (wird bei jeder Anfrage geprüft).
        CREATE TABLE berater_einladung (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_email  TEXT NOT NULL,
            bezeichnung  TEXT NOT NULL,
            token_hash   TEXT NOT NULL UNIQUE,
            expires_at   TEXT NOT NULL,
            eingeloest_am TEXT,
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE berater_zugang (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_email      TEXT NOT NULL,
            bezeichnung      TEXT NOT NULL,
            name             TEXT NOT NULL,
            email            TEXT NOT NULL UNIQUE,
            passwort_hash    TEXT NOT NULL,
            gesperrt         INTEGER NOT NULL DEFAULT 0,
            letzte_anmeldung TEXT,
            created_at       TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX idx_berater_zugang_owner ON berater_zugang(owner_email);
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
