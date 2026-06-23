# CLAUDE.md — Tab

Arbeitsanweisungen für Claude Code in diesem Repo. Kurz halten, beim Ändern aktuell halten.

## Was ist Tab

Schlanke EÜR-Buchhaltung für Einzelunternehmer mit **Kleinunternehmerregelung (§19 UStG)**.
Belege erfassen → Kategorien → am Jahresende **EÜR-Summenblatt pro Anlage-EÜR-Zeile** +
**Beleg-Journal (CSV)** exportieren. Kein ELSTER-Direktversand, kein Bankabruf, nur manuell
erfasste Belege. Multi-Gewerbe (eine EÜR pro Gewerbe). Single-User (Phase 1).
**Keine Steuerberatung.**

## Verbindliche Quellen

- **`DESIGN.md`** — UI strikt danach (Fin.Co Design System: Mint/Ink/Paper, Roboto
  self-hosted via `@fontsource`, Custom-Dropdowns statt `<select>`, Touch-Targets ≥ 44 px,
  Cards `rounded-2xl`). Nicht abweichen.
- **`EUER_KATEGORIEN.md`** — fachliche Quelle für Kategorien, Kategorie→Zeile-Mapping,
  KU-Regeln, Sonderfälle (AfA, GWG, Bewirtung 70 %, Geschenke). Bei Mapping-Fragen zuerst hier lesen.

## Architektur

- **Backend:** FastAPI + **SQLite** (eine Datei, **kein** DB-Container), stdlib `sqlite3`,
  eine Connection pro Request (`app/db.py`). Endpunkte sind sync `def` (Threadpool).
- **Migrationen:** simple Liste in `app/migrations.py` (`MIGRATIONS`, getrackt über
  `PRAGMA user_version`). **Kein Alembic.** Neue Schema-Änderung = neue `Migration(version=N, sql=...)`
  anhängen, niemals bestehende ändern.
- **Seed:** `app/seed.py`, **idempotent per ON CONFLICT DO UPDATE**. Läuft bei jedem Start
  (FastAPI-`lifespan` in `app/main.py`). Stammdaten (kategorie, euer_jahr, euer_zeile,
  euer_mapping) werden geseedet/aktualisiert; Nutzerdaten nie angefasst.
- **Auth:** Single-User aus `.env` (`ADMIN_USERNAME` + bcrypt `ADMIN_PASSWORD_HASH`),
  JWT-**Bearer** im `Authorization`-Header (`app/auth/`). Kein User-Table, keine Cookies.
  Frontend hält den Token in `localStorage` (`src/api/client.js`).
- **Frontend:** React 18 + Vite + Tailwind (JS, kein TS). Globale Filter (Gewerbe + Jahr)
  leben im `Layout` und werden via `useOutletContext()` an die Pages gereicht.

## Datenmodell (SQLite)

`gewerbe` (inkl. `besteuerung`: `kleinunternehmer`|`regelbesteuerung`), `kategorie` (stabile
Stammdaten + Flags), `euer_jahr` (VZ-Meta inkl. `vorlaeufig`), `euer_zeile` (Zeilen-Labels je
Jahr), `euer_mapping` (Kategorie→Zeile **je Jahr**), `buchung` (**Beleg-Kopf**: gewerbe_id, datum,
beschreibung), `buchung_position` (**je Position eine Kategorie + Betrag** — eine Rechnung kann
mehrere Positionen haben), `afa_buchung` (Wirtschaftsgüter), `beleg` (Datei mit `gewerbe_id` +
**nullable** `buchung_id` = Eingang/zugeordnet). Migrationen: v1 = Grundschema, v2 = `besteuerung` +
`beleg`, v3 = `buchung_position` + Beleg-Eingang (buchung→Kopf, beleg→gewerbe-bezogen, nullable).

Migrations-Runner schaltet `foreign_keys` während der Migration ab (für Tabellen-Rebuilds bei v3) und
danach wieder an. Neue Schema-Änderung = neue `Migration` anhängen; Rebuild-Migrationen via
create-new/copy/drop/rename (siehe v3).

**Geld = Integer Cent** (`*_cent`), Beträge positiv, Richtung über `kategorie.typ`.
**Buchung speichert die Kategorie, nie die Zeilennummer** — die Zeile wird beim Export aus
der Mapping-Version des Jahres aufgelöst.

## Kritische Fachregeln (nicht brechen)

- **KU = brutto.** Zeilen **15, 17, 57, 58** werden NIE befüllt (`NIE_BEFUELLT` in `seed.py`,
  Guard im Export). **Zeile 16** wird genutzt (steuerfreie Courtage §4 Nr. 11).
- **Bewirtung:** 100 % erfassen, Export rechnet **70 %** (`abzug_quote=0.7`) in Zeile 63.
- **AfA** (`app/services/afa.py`): linear, **monatsgenau pro rata** bei Nutzungsdauer > 1;
  **Vollabzug im Kaufjahr** bei Nutzungsdauer = 1 (Hardware/Software-Sofort-Option).
  Jahres-AfA fließt in Zeile 33, wird **berechnet, nicht gespeichert**.
- **GWG:** weicher Hinweis im UI (800 € netto ≈ 952 € brutto), keine harte Prüfung.
- **km-Pauschale (Zeile 71):** km-Feld im UI × 0,30 €/km (`KM_SATZ_CENT`); Backend speichert
  nur den Betrag.
- **Mapping jahres-versioniert:** 2025 verifiziert, 2026 vorläufig (`vorlaeufig=1`). Fehlt ein
  Mapping fürs Jahr → `MappingMissingError` → 400 mit klarer Meldung (kein Crash).
- ⚠ Kategorien für laufende Kosten zeigen vorläufig auf **Zeile 60** (gewinnneutral) — finale
  Zeile (43–54) beim Vordruck-Abgleich in `seed.py` setzen, dann redeployen.
- **Beleg-Eingang (`app/routes/belege.py`):** PDF/JPG/PNG, Dateien unter `UPLOAD_ROOT`
  (Prod-Bind-Mount `/opt/appdata/tab/uploads`), max. `MAX_UPLOAD_MB`. **Workflow:** erst in den
  Eingang hochladen (buchung_id NULL = offen), später per Buchung zuordnen (`beleg_ids` beim
  Anlegen oder PATCH `/belege/{id}`). Buchung löschen → Belege fallen via ON DELETE SET NULL zurück
  in den Eingang (Dateien bleiben); nur DELETE `/belege/{id}` entfernt die Datei. **Uploads ins Backup.**
- **Mehrere Positionen je Buchung:** Buchung = Beleg-Kopf, `buchung_position` = Kategorie-Splits.
  Export/Kennzahlen aggregieren über Positionen. Kategorie-Dropdown ist durchsuchbar (`searchable`).
- **KU-Status:** `gewerbe.besteuerung`. Export ist **KU-only** — bei `regelbesteuerung` liefert er
  bewusst 400 (`BesteuerungNotSupportedError`), kein falscher KU-Export.
- **PDF:** kein Server-PDF, sondern Druck-Ansicht (`window.print()` + `@media print` /
  `.print-area` in `index.css`) auf der Export-Seite.

## Tests / Validierung

Kein Test-Framework eingecheckt. Vor größeren Backend-Änderungen lohnt ein TestClient-Smoke
(venv mit `requirements.txt` + `httpx`, `TestClient(app)` **als Context-Manager**, sonst läuft
der `lifespan`/die Migrationen nicht). Frontend: `npm run build` muss durchlaufen.

## Deploy

`docker-compose.prod.yml` (Container `tab-backend`/`tab-frontend`, Netz `proxy`, keine
Host-Ports, Bind-Mount `/opt/appdata/tab/data`), `caddy.snippet` (explizite Container-Namen,
keine generischen Aliase), `scripts/deploy.sh`. Frontend baut mit getracktem
`frontend/.env.production` (`VITE_API_BASE_URL=https://tab.vrwb.de`, same-origin).

## Noch offen / nicht gebaut

- **Regelbesteuerung / USt** — Flag (`besteuerung`) existiert, aber USt-Aufschlüsselung,
  Vorsteuer, Zeilen 15/17/57/58 und der Export dafür fehlen. Braucht eine eigene Mapping-Spec
  (analog `EUER_KATEGORIEN.md`) bevor man Steuer-Zeilen festlegt — nicht raten.
- Weiterhin außen vor: Multi-User/Mandant, Bankabruf, ELSTER-Direktversand, USt-Voranmeldung.
