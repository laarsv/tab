# CLAUDE.md — Tab

Arbeitsanweisungen für Claude Code in diesem Repo. Kurz halten, beim Ändern aktuell halten.

## Was ist Tab

Schlanke EÜR-Buchhaltung für Einzelunternehmer mit **Kleinunternehmerregelung (§19 UStG)**.
Belege erfassen → Kategorien → am Jahresende **EÜR-Summenblatt pro Anlage-EÜR-Zeile** +
**Beleg-Journal (CSV)** exportieren. Kein ELSTER-Direktversand, **kein Bankabruf** (kein PSD2) — Kontoauszüge nur als
Datei (CAMT.053/CSV, siehe Bank-Import); Belege manuell, per Mail oder Handy-Teilen. Multi-Gewerbe (eine EÜR pro Gewerbe). Single-User (Phase 1).
**Keine Steuerberatung.**

## Verbindliche Quellen

- **`DESIGN.md`** — **verbindliche Marken-/Farbnorm: VRWB CI v1.0, Royal Blue.** Tokens
  `royal` (`#2947c9`/soft `#aeb9ee`), `ink` `#161a24`, `paper`. **Kontrastregel (wichtig, anders
  als bei Mint):** Royal ist ein *dunkler* Akzent → Text auf **gefüllten** Royal-Flächen ist
  **weiß (`paper`)** (`.btn-primary`, Badges); Royal als *Textfarbe* auf Weiß ist ok (Nav aktiv,
  Eyebrow, Links). **Tool-Marke** (CI-Konvention, Details + Quelle in DESIGN.md §1b;
  zentral in `components/Wordmark.jsx` — nie inline nachbauen): **Royal-Seitenleiste =
  `Wordmark onRoyal`** (weiß, `_tab` weiß 80 %; seit dem Recap-Umbau 2026-10-27 statt
  `SignaturLockup`, der bleibt ungenutzt in der Datei); **Login/Titel = Standalone `vrwb_tab`** (`vrwb` Roboto 900
  −4,5 %, `_tab` Royal, Toolname Roboto Mono 500 0,83× −1 %, immer klein; auf Ink `_tab`
  Royal Soft). Favicon `t_` auf Royal (`public/favicon.svg`). Roboto + Roboto Mono
  self-hosted, kein Google-CDN. `theme-color = #2947c9`.
- **`DESIGN.shared.md`** — Dichte-/Komponenten-Konventionen (Dichte v2): 44 px Touch **mobil**,
  Desktop kompakt (~32–36 px) — Tipp-Felder `py-2.5 text-base` auf Base, ab `sm:` `py-1.5 text-sm`
  (iOS-Zoom-Schutz nie brechen). `.field-label` (dezent), `.eyebrow`, Formular-Grids `gap-x-5 gap-y-2`,
  Ghost-Select für Inline-Werte. Zentrale Klassen in `src/index.css`
  (`.btn/.btn-sm/.input/.field-label/.eyebrow/.card`), Select in `components/Dropdown.jsx`
  (`variant="ghost"`). **Karten-Aktionen = Icon-Buttons** (`components/Icons.jsx` → `IconButton` mit
  `title`+`aria-label`, Klassen `.btn-icon-*` in `index.css`; Klassennamen nie dynamisch zusammensetzen —
  Tailwind findet sie sonst nicht). **Diese Muster gelten weiter — nur die Palette ist Royal statt Mint** (DESIGN.md gewinnt bei Farbe/Kontrast).
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
- **Auth:** **Google OAuth** (Authlib, wie die anderen Tools) — `app/auth/` (`google.py`,
  `router.py` login/callback/logout/me, `session.py` JWT, `cookies.py`, `deps.py`). Session als
  **HttpOnly-JWT-Cookie** (`COOKIE_NAME`), OAuth-State via Starlette-`SessionMiddleware`
  (`SESSION_SECRET`). Single-User über **E-Mail-Allowlist** (`ALLOWED_EMAILS`, kein User-Table,
  da Gmail keine Domain-Allowlist erlaubt); `get_current_user` prüft die Allowlist bei jedem
  Request. Frontend nutzt **Cookies** (`withCredentials`, kein localStorage/Bearer), Login = Full-Page
  auf `/api/auth/login`. Setup: OAuth-Client in Google Cloud, Redirect-URI
  `https://tab.vrwb.de/api/auth/callback`, `.env` (GOOGLE_CLIENT_ID/SECRET, ALLOWED_EMAILS,
  JWT_SECRET, SESSION_SECRET).
- **Frontend:** React 18 + Vite + Tailwind (JS, kein TS). Globale Filter (Gewerbe + Jahr)
  leben im `Layout` und werden via `useOutletContext()` an die Pages gereicht.

## Datenmodell (SQLite)

`gewerbe` (inkl. `besteuerung`: `kleinunternehmer`|`regelbesteuerung`), `kategorie` (stabile
Stammdaten + Flags), `euer_jahr` (VZ-Meta inkl. `vorlaeufig`), `euer_zeile` (Zeilen-Labels je
Jahr), `euer_mapping` (Kategorie→Zeile **je Jahr**), `buchung` (**Beleg-Kopf**: gewerbe_id, datum,
beschreibung), `buchung_position` (**je Position eine Kategorie + Betrag** — eine Rechnung kann
mehrere Positionen haben), `afa_buchung` (Wirtschaftsgüter, inkl. **nullable `abgang_datum`**),
`beleg` (Datei mit `gewerbe_id` + **nullable** `buchung_id` = Eingang/zugeordnet). Migrationen:
v1 = Grundschema, v2 = `besteuerung` + `beleg`, v3 = `buchung_position` + Beleg-Eingang
(buchung→Kopf, beleg→gewerbe-bezogen, nullable), v4 = `afa_buchung.abgang_datum`,
v5 = `fahrt` (Fahrten-Liste für die km-Pauschale), v6 = Rechnungsmodul (`rechnung`,
`rechnung_position`, `user_mail`) + Gewerbe-Absenderfelder (`anschrift`, `iban`,
`rechnung_fusszeile`), v7 = `rechnung.steuerhinweis`, v8 = `rechnung_abo`
(wiederkehrende Rechnungen, Positionen als JSON), v9 = `kontakt` (inkl. Backfill
aus bestehenden Rechnungen), v10 = `beleg.faellig_am` („noch zu zahlen"-Erinnerung
im Eingang; offene Belege sortieren fällige zuerst, PATCH nutzt model_fields_set),
v11 = Mail-Import (`user_mail.import_*` + Dedup-Tabelle `mail_import`), v15 = `rechnung.buchung_id` (Rechnung↔Einnahme-Buchung, ON DELETE SET NULL; Backfill über „Rechnung {nr} – …“), v16 = `news_gelesen` (Neuigkeiten gelesen je Login), v17 = Fälligkeit + Mahnwesen
(`rechnung.zahlungsziel_tage`/`faellig_am`, Gewerbe-Einstellungen `zahlungsziel_tage`/`mahn_frist_tage`/`mahn_gebuehr_{1,2,3}_cent`/`basiszinssatz_bp`, Tabelle `mahnung`), v18 = `gewerbe.kontoinhaber`, v19 = `frist_einstellung` + `frist_erledigt` (Fristen-Seite), v20 = `audit_log` + `jahr_abschluss` (Festschreibung; die Trigger legt `services/audit.ensure_triggers()` bei jedem Start an), v21 = `bankkonto` + `bank_import` + `bank_umsatz` (Bank-Import), v22 = `rechnung_zahlung` + `rechnung.skonto_bp`/`skonto_tage` (Teilzahlungen, Skonto), v23 = `angebot` + `angebot_position` (Angebote), v24 = `buchung_position.privat_bp` + `dauerbeleg` + `buchung.dauerbeleg_id`/`termin` (Privatanteil, Dauerbelege), v25 = `afa_buchung.degressiv_bp`/`linear_ab_jahr` (AfA-Methoden). v26 = `rechnung.bestellnummer`, `gewerbe.logo_datei`, `artikel`, `textbaustein` (Rechnungs-Komfort). v27 = `berater_einladung` + `berater_zugang` (Zugang für die Steuerberatung). v28 = `passkey` (Passkeys). v29 = `ki_token` (KI-Assistenten/MCP). v30 = `oauth_client` + `oauth_code` + `oauth_grant` (OAuth für MCP). v31 = `ki_vorschlag` + `vorschlaege` an `ki_token`/`oauth_code`/`oauth_grant` (KI-Änderungsvorschläge).

Migrations-Runner schaltet `foreign_keys` während der Migration ab (für Tabellen-Rebuilds bei v3) und
danach wieder an. Neue Schema-Änderung = neue `Migration` anhängen; Rebuild-Migrationen via
create-new/copy/drop/rename (siehe v3).

**Geld = Integer Cent** (`*_cent`), Beträge positiv, Richtung über `kategorie.typ`.
**Buchung speichert die Kategorie, nie die Zeilennummer** — die Zeile wird beim Export aus
der Mapping-Version des Jahres aufgelöst.

## Kritische Fachregeln (nicht brechen)

- **KU = brutto.** Zeilen **15, 17** sowie Vorsteuer und an das Finanzamt gezahlte USt werden NIE
  befüllt — das sind **2025: 15, 17, 57, 58**, **2026: 15, 17, 58, 59** (`NIE_BEFUELLT_JE_JAHR`
  in `seed.py`, Guard im Export; 2026 ist Z57 „Übrige Schuldzinsen" und ganz normal befüllbar).
  **Zeile 16** wird genutzt (steuerfreie Courtage §4 Nr. 11).
- **Zeilennummern wandern jährlich:** `ZEILEN_<jahr>`/`MAPPING_<jahr>` in `seed.py` sind je Jahr
  getrennt (nie ein Jahr aus dem anderen ableiten). 2026 hat eine neue Zeile 27 (Rücklage
  Tierbewertung, nur Land-/Forstwirte) + Übertrag Z28 → Waren Z29 (2025: Z27), ab da fast alles +1
  (u. a. AfA 33→34, GWG 36→37, Restbuchwert 38→39, Bewirtung 63→64, km-Pauschale 71→72,
  Entfernungspauschale 73→74). Texte im Frontend nehmen die Zeile aus `/api/kategorien?jahr=` —
  keine Zeilennummern hartcodieren.
- **Bewirtung:** 100 % erfassen, Export rechnet **70 %** (`abzug_quote=0.7`) in die Bewirtungszeile
  (2025: 63, 2026: 64).
- **AfA** (`app/services/afa.py`): linear, **monatsgenau pro rata** bei Nutzungsdauer > 1;
  **Vollabzug im Kaufjahr** bei Nutzungsdauer = 1 (Hardware/Software-Sofort-Option).
  Jahres-AfA fließt in die AfA-Zeile (2025: 33, 2026: 34), wird **berechnet, nicht gespeichert**. **Abgang**
  (`abgang_datum`): AfA endet mit dem Abgangsmonat; `restbuchwert_cent` wird berechnet und im
  UI als Hinweis gezeigt (manuell als Buchung in der Restbuchwert-Zeile erfassen, Erlös Zeile 19).
- **AfA-Methoden (`afa_buchung.afa_methode`, `degressiv_bp`, `linear_ab_jahr`, v25; Aufbau nach Haben):**
  `linear` (Standard; die Rechnung ist seit jeher unverändert, Altanlagen und alte Siegel rechnen gleich),
  `degressiv` (§ 7 Abs. 2 EStG), `elektro` (§ 7 Abs. 2a), `sammelposten` (§ 6 Abs. 2a). **Alles läuft über
  `services/afa.verlauf()`** (Plan je Jahr mit Buchwert); `afa_jahr(row, jahr)`, `afa_restbuchwert(row)` und
  `methode_text(row)` sind die Einstiege für Export, Siegel und Liste — nie `jahres_afa_cent` mit Teilfeldern
  direkt aufrufen. **Degressiv:** fester Satz vom Buchwert am Jahresanfang, im Anschaffungsjahr ab dem
  Anschaffungsmonat; **Wechsel zur linearen AfA**, sobald diese (Buchwert / Restmonate) ≥ der degressiven ist
  (§ 7 Abs. 3), oder ab `linear_ab_jahr`. Zulässig nur für Anschaffungen **01.07.2025–31.12.2027** (höchstens
  Dreifaches des linearen Satzes, max. 30 %), **01.04.–31.12.2024** (2×, max. 20 %), **2020–2022** (2,5×, max.
  25 %) und Nutzungsdauer ≥ 2 — `degressiv_grenze()` ist die einzige Quelle; ohne Satz gilt der Höchstsatz.
  Kontrolle gegen Habens Rechenbeispiel (100.000 €, 30 %, ND 10) auf den Cent im Test. **Elektro:** Staffel
  75/10/5/5/3/2 % der AK, Anschaffung 01.07.2025–31.12.2027, Dauer fest 6 Jahre; bei Abgang zählt das Jahr
  zeitanteilig bis zum Abgangsmonat. Ob es wirklich ein reines E-Fahrzeug ist, prüft Tab nicht (Nutzer
  entscheidet). **Sammelposten:** je ein Fünftel im Anschaffungsjahr und den vier Folgejahren, unabhängig vom
  Monat, Dauer fest 5; **ein Abgang ändert nichts** (kein Restbuchwert) — deshalb gilt die Jahres-Sperre für
  Sammelposten auch nach dem Abgangsjahr (`_afa_betrifft` in `audit.py` und `abschluss.py`). Die Grenzen
  250,01–1.000 € sind nur ein **weicher Hinweis** (kommt als `hinweise` aus der API, mit dem Hinweis auf das
  einheitliche Wahlrecht je Wirtschaftsjahr). **Elektro/Sammelposten setzen die Nutzungsdauer selbst.**
  **Formular:** `GET /api/afa/optionen` (zulässige Methoden + Höchstsatz) und `POST /api/afa/vorschau` (Plan vor
  dem Speichern); Methoden, die für das Datum nicht gelten, fallen auf linear zurück. **Sperre/Siegel:**
  `afa_methode`/`degressiv_bp`/`linear_ab_jahr` sind in abgeschlossenen Jahren gesperrt (Trigger), im Siegel
  stecken Satz und Wechseljahr nur, wenn gesetzt (Siegel vor v25 bleiben nachrechenbar). Das Journal nennt bei
  nicht linearen Anlagen die Methode statt „ND n J.“. Nicht gebaut: Erinnerungswert 1 €, Übernahme mit
  Restbuchwert zum Stichtag (Tab rechnet immer ab dem Anschaffungsdatum), Anlage AVEÜR, Sonderabschreibung
  § 7g, Antriebsprüfung beim E-Fahrzeug.
- **GWG:** Grenze **800 € inkl. USt** (Kleinunternehmer haben keinen Vorsteuerabzug, § 6 Abs. 2 EStG; die
  frühere Lesart „800 € netto ≈ 952 € brutto" gilt nur für Regelbesteuerer — nicht zurückdrehen). Weicher
  Hinweis + gelbe Warnung ab 800 € im BuchungModal (`GWG_GRENZE_CENT`), keine harte Prüfung. Weitere
  Soft-Hinweise: Geschenke > 50 € (Freigrenze), Homeoffice > 1.260 €/Jahr.
- **Rechner-Helfer (`BuchungModal.jsx`, `CALCULATORS`):** Fahrtkosten (km × 0,30 €),
  Entfernungspauschale (Tage × km; **bis 2025** 0,30 €, ab km 21 0,38 € — **ab 2026** 0,38 € vom
  1. km an, der Rechner nimmt das Jahr aus dem Buchungsdatum), Homeoffice (Tage × 6 €),
  Verpflegungsmehraufwand (28/14 €), 1 %-Regelung (Listenpreis × Antriebs-Satz 1/0,5/0,25
  für Verbrenner/Hybrid/E-Auto, auf 100 € abgerundet, × Monate; Select-Feldtyp im
  CALCULATORS-Framework). Sie **füllen nur das Betragsfeld** — das Betragsfeld bleibt
  Quelle der Wahrheit, Backend speichert nur den Betrag (Edit-sicher).
- **1 %-Regelung (Betriebs-Kfz), bewusst schlank:** Entnahme = Einnahme-Kategorie
  `kfz_privatnutzung` (Zeile 20), Kosten = `kfz_kosten` (2026: Z71 „Sonstige tatsächliche
  Fahrtkosten"; Leasing wäre Z69, Steuer/Versicherung Z70 — nicht getrennt; 2025 noch Z60).
  NICHT abgedeckt: 0,03 %-Wege-Kürzung (2026: Z73), Kostendeckelung, Fahrtenbuch. Die Entnahme
  zählt nicht in `ku_umsatz` (Vereinfachung, siehe EUER_KATEGORIEN.md §4.6).
- **KU-Grenz-Guard (`/api/kennzahlen`):** Grenzvergleich (25.000/100.000 €) läuft über
  `ku_umsatz_cent` = nur Kategorie `einnahme_ku` — steuerfreie Courtage (§4 Nr. 11) und
  Anlagenverkäufe bleiben nach §19 Abs. 2 UStG außer Ansatz.
- **Mapping jahres-versioniert:** 2025 und 2026 gegen den amtlichen Vordruck verifiziert
  (BMF-Schreiben 29.08.2025 / 01.09.2026, `vorlaeufig=0`). Fehlt ein Mapping fürs Jahr **oder für
  eine bebuchte Kategorie** → `MappingMissingError` → 400 mit klarer Meldung (kein stilles
  Weglassen von Beträgen). `seed.py` prüft beim Start, dass jede Kategorie je Jahr gemappt ist und
  jede Ziel-Zeile in den Zeilen-Stammdaten steht; veraltete `euer_zeile`-Einträge werden gelöscht.
  **2026: alle laufenden Kosten final** (Telekom 44, Fortbildung 46, Rechts/Steuer 47, Miete/Leasing
  48, Reparatur 49, Versicherung + Gebühren 50, Werbung 55, Zinsen 57, Personal 31; Software/Büro/
  Konto bewusst „übrige" Z61). **2025: laufende Kosten weiter auf der gewinnneutralen Z60**
  (Vordruck-Zeilen stehen als Kommentar im Seed) — nur Miete (Z39) und sonstige Entnahmen (Z21)
  sind korrigiert.
- **Neues Jahr aufnehmen (jährlich ab Herbst):** BMF-Schreiben „Anlage EÜR <jahr>" (Vordruck-PDF
  + Anleitung) laden und die Seiten 3–5 des Vordrucks **ansehen** (Text-Extraktion vermischt die
  Spalten), dann `ZEILEN_<jahr>`/`MAPPING_<jahr>`/`NIE_BEFUELLT_JE_JAHR`/`JAHRE` ergänzen, Anleitung
  auf Rechenregeln prüfen (Pauschalen, Entfernungspauschale, Grenzen), deployen.
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
- **Export-Downloads:** Summenblatt/Journal-CSV, **Jahres-Archiv** `/api/export/belege.zip`
  (CSVs + Beleg-Dateien der Buchungen des Jahres) und **Backup** `/api/export/backup.zip`
  (SQLite-Snapshot via backup-API + alle Uploads).
- **CSV-Import** (`POST /api/buchungen/import`): Semikolon-CSV
  `Datum;Betrag;Kategorie[;Beschreibung[;Beleg-Details]]`, Datum TT.MM.JJJJ oder ISO, Betrag
  deutsch, Kategorie = Key oder Name. **Alles-oder-nichts** — bei Fehlern 400 mit Zeilenliste.
- **Datum≠Jahr-Hinweis:** BuchungModal warnt (weich), wenn das Buchungsdatum nicht im global
  gewählten Jahr liegt — sonst „verschwindet" die Buchung hinter dem Jahresfilter.
- **Neuigkeiten (`lib/neuigkeiten.js` + `NeuigkeitenModal`):** Bei jedem größeren Feature
  einen Eintrag ERGÄNZEN (id hochzählen, neueste zuerst) — das Fenster öffnet beim nächsten
  Login automatisch, sonst über Profil-Menü „Neuigkeiten". **Gelesen-Stand je ACCOUNT auf dem
  Server** (`routes/news.py`, Tabelle `news_gelesen`, v16; GET `/api/news`, POST
  `/api/news/gelesen`) — localStorage (`tab_news_gelesen:{email}`) ist nur Cache/Offline-Fallback
  und wird beim Start per `syncGelesen` mit dem Server vereinigt (altes Format
  `tab_news_gelesen`/`tab_news_gesehen` wird übernommen). Nur die Einzel-Bestätigung zählt,
  Schließen nicht. Vorher (nur localStorage) kam das Fenster auf jedem Gerät/Browser/in der PWA wieder.
- **Einrichtung & Hilfe (`/einrichtung`, `pages/Einrichtung.jsx`):** geführter 5-Schritte-
  Wizard (Gewerbe/Absender, App-Passwort, Mail-Import, PWA aufs Handy, erste Buchungen) —
  Status wo möglich automatisch aus echten Daten, PWA per Haken (localStorage
  `tab_setup_haken`). Detail-Anleitungen für App-Passwort/+tab-Adresse/PWA leben HIER
  (nicht duplizieren). `openMailSetup` kommt aus dem Layout-Context.
- **Layout = Royal-Seitenleiste (Recap-Stil, 2026-10-27, DESIGN.md §6):** `components/Layout.jsx`
  (Rahmen, lädt Gewerbe/Jahre/Badges/Eingang-Zähler) + `components/Sidebar.jsx` (262 px, ab `lg`
  fest links; darunter dieselbe Leiste als **Schublade** + Royal-Leiste oben + **Tab-Leiste unten**
  mit Übersicht/Buchungen/Rechnungen/Check/Mehr). Inhalt: Wortmarke, „Neue Buchung" + Upload-Icon,
  Gewerbe/Jahr-Kapseln, **„Jetzt"-Zeile = Beleg-Eingang** (nur wenn etwas wartet), Nav
  (Übersicht · Buchungen · Rechnungen · Jahres-Check mit Badge · Abschreibungen), „Weitere" (Export, Gewerbe,
  Einrichtung & Hilfe), unten die Profilzeile (Menü: E-Mail-Versand, Neuigkeiten, Abmelden).
  **Keine Wellen** (Lars: die sind recap-Sprache). Aufrufe von außen per URL an `/buchungen`:
  `?neu=…` öffnet das BuchungModal, `?abarbeiten=…` startet den Eingang-Wizard, `?geteilt=…` ist
  der PWA-Share-Toast. Hochladen steckt im Layout (`uploadBelege` im Outlet-Context, danach zählt
  `eingangTick` hoch und die Seite lädt neu). Der Beleg-Eingang ist **in die Buchungen-Seite
  integriert** (Zeilen, „Jetzt abarbeiten", Upload); `/eingang` redirectet auf `/buchungen`.
  **Zeilen statt Karten (alle Seiten):** `components/PageParts.jsx` (`PageHeader`, `SectionHead`,
  `Row` mit `kind`/`leading`/`children`/`muted`, `Zustand`, `Hinweis`, `Kennzahlen`/`Kennzahl`,
  `Fortschritt`, `Leer`, `KeinGewerbe`), `.page-title`, `.card` ist flach. Zustände sind Wörter in
  Zustandsfarbe in der Zustandszeile (`Zustand`), keine Chips; Aktionen Icon-Knöpfe, Text nur bei
  der einen Hauptaktion oder wenn das Icon mehrdeutig ist (z. B. „+ Einnahme buchen" im
  Jahres-Check). Neue Seiten/Listen nur noch mit diesen Bausteinen bauen. **Dialoge:** `Modal`
  (Titel 26/900, `subtitle`, Kreuz) + `components/DialogParts.jsx` (`SchalterZeile` statt Häkchen,
  `DialogFuss`, `Gruppe`, `PositionenEditor`) — keine nativen Checkboxen und keine Rahmen-Kästen mehr.
- **Übersicht (`/uebersicht`, `pages/Uebersicht.jsx`, `routes/uebersicht.py`, Startseite):** Aufbau nach Haben
  (Kennzahlen + Aufgabenliste „Zu erledigen“ + offene/letzte Zeilen), **rechnet nichts selbst** — `GET
  /api/uebersicht?gewerbe_id=&jahr=` sammelt aus vorhandenen Diensten: Kennzahlen (`services/kennzahlen.py`,
  gemeinsam mit `/api/kennzahlen` und Vorjahr), Forderungen (versendete Rechnungen mit offenem Rest über
  `zahlungen.offen_cent`, Fälligkeit über `mahnwesen.effektive_faelligkeit`), `aufgaben` und die letzten 5 Buchungen
  (jahresunabhängig). **Aufgaben** nur, was wirklich offen ist, je mit `ton` (`neg` überfällig → `warn` → `leise`,
  stabil sortiert), Ziel und der einen Hauptaktion: überfällige Rechnungen (→ Mahnwesen), dringende Steuerfrist
  (gleiche Regel wie der Zähler an „Fristen“, `fristen_des_nutzers`), fällige Dauerbeleg-Termine, Beleg-Eingang
  (startet den Wizard, `?abarbeiten=`), Bankumsätze ohne Zuordnung, Rechnungsentwürfe, Angebote ohne Antwort,
  jüngstes nicht abgeschlossenes Vorjahr mit Buchungen. Der **Jahres-Check** kommt nur aus dem Frontend (sein Stand
  liegt in localStorage, `checkOffen` aus dem Layout-Context) und wird als letzte Zeile angehängt. Neue
  Aufgabenart = Block in `_aufgaben()` + Icon in `ICON` (Uebersicht.jsx). `KuGuard` (Warnband bei Überschreiten der
  KU-Grenzen) lebt in `components/KuGuard.jsx` und läuft auf Buchungen und Übersicht. Login, OAuth-Callback und
  Wortmarke führen hierher (`*` → `/uebersicht`). Nicht gebaut: Monatsverlauf/Diagramm, Kontostand, Einnahmen-
  Vergleich über mehrere Gewerbe, frei wählbare Kacheln.
- **Aus vrwb_flow übernommen (2026-11-14, Details DESIGN.md §4):** Überfälliges ist **Bernstein** (`kind`/`ton` `late`), Rot nur
  für Fehler und harte Endzustände; Fristen stehen **in Worten** (`<Frist>` aus `PageParts.jsx`, `lib/fristWorte.js`; Mahnwesen
  behält genaue Verzugstage); Leiste **„Neue Version verfügbar“** (`components/NeueVersion.jsx` in `main.jsx`, vergleicht
  das laufende `assets/index-<hash>.js` mit dem der frischen `index.html`, nie automatisches Neuladen; `index.html` wird mit
  `no-cache` ausgeliefert). Neue Listen: überfällig nie mit `neg`. **Einstellungen als ein Fenster** (`components/EinstellungenFenster.jsx`, Bereiche E-Mail,
  Passkeys, KI-Assistenten, Steuerberatung; geöffnet über Profil-Menü → Einstellungen oder `openEinstellungen(bereich)` /
  `openMailSetup` aus dem Layout-Context; „Steuerberatung“ steht nicht mehr in der Seitenleiste, die Route `/steuerberatung`
  gibt es weiter). Wo ältere Abschnitte „Profil-Menü → Passkeys/KI-Assistenten/E-Mail-Versand“ sagen, ist dieses Fenster gemeint. **Rechnungen ab 1280 px: Liste links, offene Rechnung rechts** (`RechnungsListe` in `pages/Rechnungen.jsx`, eine Hauptaktion über `hauptaktion()`, Rest Icons; darunter die gewohnten Zeilen; beide nutzen `zustandZeile`/`aktionen`/`verlauf`).
- **Eingang-Wizard:** „Jetzt abarbeiten (N)" führt Beleg für Beleg durchs BuchungModal
  (`wizard`-Prop: Titel „Beleg X von Y", Überspringen-Button). Queue = Snapshot beim Start;
  `key={beleg.id}` remountet das Modal je Beleg.
- **Jahres-Check (`/check`, `pages/JahresCheck.jsx` + `lib/jahresCheck.js`):** geführte
  Themenliste für Einsteiger (Auto, Handy, Homeoffice, Bewirtung …). Status kommt automatisch
  aus den Buchungen des Jahres (Summe je Kategorie-Key); **Info-Themen** (`info: true`, z. B.
  §19-Hinweis, Steuer-Rücklage, Gründungskosten) werden per Erledigt-Haken abgehakt.
  „Nicht relevant"/„Erledigt" liegen in localStorage (`tab_check_{gewerbe}_{jahr}`,
  `loadCheckState`). Aktionen öffnen das BuchungModal mit `presetKategorieId` (+ optional
  `presetBetragCent`/`presetBeschreibung`); `links` verlinken Seiten. Dazu die statische
  „Gehört NICHT hierher"-Karte (`NICHT_ABSETZBAR`). Themen ändern = `lib/jahresCheck.js`.
- **Fahrten-Liste (`/fahrten`, `routes/fahrten.py`, Tabelle `fahrt`):** Nachweis-Liste für die
  km-Pauschale (Privatwagen, 2025 Zeile 71 / 2026 Zeile 72) — Datum/Ziel/Anlass/km, Summe × 0,30 € per Klick als
  Buchung (fahrtkosten_kfz) übernehmen. **Bewusst KEIN Fahrtenbuch** i. S. d. 1 %-Alternative
  (Unveränderbarkeits-Anforderungen kann Tab nicht erfüllen — nicht versprechen!). Die Liste
  landet als `fahrten-{jahr}.csv` im Jahres-ZIP. Nicht in der Nav — verlinkt aus dem
  Jahres-Check (Auto-Thema).
- **E-Rechnung (Empfang):** Beleg-Eingang akzeptiert **XML** (XRechnung/ZUGFeRD) —
  Empfangs-/Archivpflicht gilt seit 2025 auch für KU; Parsing via `beleg_extract`.
- **E-Rechnung (Erstellung, `services/e_rechnung.py`):** ausgehende Rechnungs-PDFs sind
  **ZUGFeRD/Factur-X (Profil EN 16931)** — handgebautes CII-XML (KU: Steuerkategorie „E",
  Steuer-Hinweis als ExemptionReason, Steuernummer schemeID FC) + Einbettung via
  `factur-x`-Lib (`check_xsd=True`). `rechnungs_pdf()` ist der einzige Einstieg für
  Download/Versand/Abo; **schlägt die Einbettung fehl → normale PDF, nie blockieren**.
  Anschriften werden tolerant geparst (`parse_anschrift`, PLZ-Muster, Land fix DE).
  Bewusst außen vor: B2G/Leitweg-ID, reines XRechnung-XML ohne PDF.
- **Rechnungsmodul (`/rechnungen`, `routes/rechnungen.py`):** KU-Rechnungen mit allen
  Pflichtangaben; **Steuer-Hinweis je Rechnung wählbar** (`steuerhinweis`, v7): `ku19`
  (§19-Satz, Default) oder `vers4nr11` (steuerfreie Versicherungsvermittlung §4 Nr. 11) —
  Texte in `STEUERHINWEISE` (`services/rechnung_pdf.py`, fpdf2, Beträge als „EUR" — € nicht
  im Core-Font). Nummer = `{jahr}-{lauf:04d}` fortlaufend je Gewerbe+Jahr, vergeben beim
  Anlegen; **Löschen nur letzte Nummer + nie nach Versand/Bezahlung** (sonst stornieren,
  keine Nummernlücken); Inhalt editierbar nur im Status `entwurf`. „Als Einnahme buchen"
  öffnet das BuchungModal vorbefüllt — `vers4nr11` → Kategorie `einnahme_steuerfrei`
  (Zeile 16), sonst `einnahme_ku` (Zeile 12); bewusst keine automatische Buchung.
  Das Modal schickt `rechnung_id` mit (BuchungModal-Prop `rechnungId`); gebucht wird seit v22 je
  **Zahlung** (siehe „Zahlungen auf Rechnungen“), `rechnung.buchung_id` zeigt nur noch auf die zuletzt
  gebuchte Zahlung. 409, wenn alles Gezahlte schon gebucht ist; Buchung löschen → die Zahlung ist wieder „ungebucht“.
- **Rechnungs-Komfort (v26, `routes/vorlagen.py`, `services/logo.py`, `components/Vorlagen.jsx` + `VorlagenModal.jsx` +
  `LogoFeld.jsx`):** Aufbau nach Haben, schlank für Kleinunternehmer. **Bestellnummer** (`rechnung.bestellnummer`,
  „Ihre Bestellnummer“, max. 80 Zeichen): Feld im Rechnungsfenster, PDF-Meta „Ihre Bestellnr.“ und in der E-Rechnung
  als **BT-13** (`BuyerOrderReferencedDocument/IssuerAssignedID` nach `BuyerTradeParty`, XSD-geprüft im Test); wie der
  übrige Inhalt nur im Entwurf änderbar. Abos und Angebot→Rechnung tragen sie nicht mit. **Artikelkatalog** (`artikel`:
  Bezeichnung + Preis in Cent, eindeutig je Gewerbe case-insensitiv; kein Steuersatz/keine Einheit — Positionen haben
  beides nicht): `POST /api/artikel` ist ein Upsert (201 neu, 200 Preis aktualisiert), im `PositionenEditor` (Prop
  `gewerbeId`, wirkt in Rechnung, Angebot und Abo) per Auswahl „Aus dem Katalog einfügen“, Lesezeichen „Als Artikel
  speichern“ und automatischem Preis, wenn die getippte Bezeichnung genau passt. **Textbausteine** (`textbaustein`:
  Name + Text bis 2000 Zeichen): „Textbaustein einfügen“ hängt den Text als neuen Absatz an Notiz der Rechnung bzw.
  Einleitung/Hinweis des Angebots. Verwaltung für beides: Knopf „Artikel & Texte“ auf Rechnungen und Angebote
  (`VorlagenModal`). Rechnungen/Angebote speichern immer eigene Werte — Katalog ändern oder löschen berührt sie nicht.
  **Logo** (`gewerbe.logo_datei`, Datei `UPLOAD_ROOT/logos/{gewerbe_id}.png`): Upload im Gewerbe-Dialog (PNG/JPG ≤ 2 MB,
  ≤ 4000 px, wird geprüft, auf 900×360 verkleinert und als PNG mit Transparenz gespeichert), `POST/GET/DELETE
  /api/gewerbe/{id}/logo`; die Gewerbe-API gibt nur `hat_logo` aus, nie den Dateinamen. `services/logo.zeichne_logo`
  setzt es oben rechts (≤ 50 × 17 mm) auf Rechnung, Mahnung und Angebot und **blockiert nie** (fehlende/kaputte Datei →
  PDF ohne Logo). Liegt im Uploads-Ordner, also im Backup. Nicht gebaut: Einheit/Steuersatz am Artikel, Artikelnummer,
  CSV-Import, Textbausteine je Kunde, Logo-Position/-Größe einstellbar, Bestellnummer im Abo.
- **Zugang für die Steuerberatung (`/steuerberatung` für den Inhaber, `/berater` für die Steuerberatung; v27,
  `routes/berater.py`, `auth/berater_guard.py`, `pages/Steuerberatung.jsx` + `Einladung.jsx` + `Berater.jsx` +
  `components/BeraterLayout.jsx`):** Aufbau nach Haben, **nur lesen**. Inhaber erzeugt einen Einladungslink (Token einmal
  sichtbar, gespeichert nur der SHA-256, einmal einlösbar, 72 h); die Steuerberatung legt damit ihr Konto an (Name,
  E-Mail, Passwort ≥ 12 Zeichen) und meldet sich später über „Zugang für die Steuerberatung“ auf der Anmeldeseite an
  (`POST /api/berater/login`, scrypt, Fehlversuch-Bremse wie `auth/local.py`, funktioniert ohne System-Mail). Eigene
  Konten in `berater_zugang`, **nicht** in `nutzer`; eine E-Mail = ein Zugang (für mehrere Mandanten braucht die Kanzlei
  je eine Adresse). **Sitzung:** JWT mit `email` = die des Inhabers + Claim `berater` = Zugangs-ID (7 Tage); so greifen
  alle Mandanten-Guards (`check_gewerbe`) unverändert, `get_current_user` liefert `rolle: "steuerberatung"` und prüft den
  Zugang bei JEDEM Request (gesperrt/entfernt/anderer Inhaber → 401, wirkt sofort). **Rechte als Allowlist** in
  `auth/berater_guard.py` (Middleware in `main.py`, läuft vor jeder Route): nur GET auf Gewerbe, Kategorien, Kennzahlen,
  Buchungen (+ Belege, Download), Rechnungen (Liste ohne Entwürfe, PDF), Anlagen, Fahrten, Export (Summenblatt, Journal,
  Jahres-ZIP), Abschluss-Stand/Protokoll; alles andere 403 — **neue Routen sind für die Steuerberatung automatisch zu**,
  bis sie dort eingetragen werden (der Test `berater_test.py` ruft jede registrierte Route auf). `ist_admin()` ist für sie
  immer False (kein Backup), `nur_inhaber` schützt die Verwaltungsrouten, `db._akteur` meldet sie als `berater:<id>`.
  Nicht für die Steuerberatung: Bank, Dauerbelege, Angebote, Kontakte, Artikel, Einstellungen, Fristen, Übersicht,
  Backup. Nicht gebaut: Passkeys, Anmelde-Protokoll im Änderungsprotokoll (nur `letzte_anmeldung`), „Neu seit dem
  letzten Besuch“, Vorschau der Beraterseite für den Inhaber, mehrere Mandanten je Konto, Rückfragen am Beleg.
- **Passkeys (v28, `routes/passkeys.py`, `lib/passkey.js`, `components/PasskeyModal.jsx`):** WebAuthn als **zusätzlicher**
  Anmeldeweg für Google- und Passwort-Konten (Bibliothek `webauthn` 2.7.1 — braucht `cryptography>=44.0.2` und
  `pyOpenSSL==25.0.0`, beides in `requirements.txt` gepinnt; pyOpenSSL 26 verlangt ein neueres cryptography). Wer
  angemeldet ist, legt im Profil-Menü → „Passkeys“ welche an (`/registrierung/optionen` + `/registrierung`, max. 10 je
  Konto, auffindbare Passkeys, **Nutzerprüfung Pflicht** — der Passkey ersetzt das Passwort); auf der Anmeldeseite genügt
  „Mit Passkey anmelden“ (`/anmeldung/optionen` + `/anmeldung`, öffentlich, keine E-Mail-Eingabe). Der Passkey gehört
  zur E-Mail des Kontos (`passkey.email`); die Anmeldung setzt das normale Session-Cookie und prüft dieselbe
  Zugangsregel wie Google/Passwort (`OPEN_SIGNUP`/`ALLOWED_EMAILS` → sonst 403). **Challenges** liegen im Speicher
  (ein Uvicorn-Prozess), 5 Minuten, genau einmal, bei der Registrierung an das Konto gebunden. Zähler gegen geklonte
  Schlüssel: steigt `sign_count` nicht, scheitert die Anmeldung. Jeder Prüffehler (auch kaputtes JSON) → 400 ohne
  Details. **RP-ID/Origin** kommen aus `FRONTEND_URL` (`PASSKEY_RP_ID`/`PASSKEY_ORIGIN` nur für Tests/Entwicklung) — die
  RP-ID ist an die Passkeys gebunden, ein späterer Domainwechsel macht sie unbrauchbar. Die Steuerberatung hat keine
  Passkeys (`nur_inhaber` + Allowlist). `passkey_test.py` nutzt einen virtuellen Authenticator (EC P-256, Format
  „none“); mit einem echten Gerät ist es nicht getestet. Nicht gebaut: Passkey für die Steuerberatung, Anmelde-Protokoll,
  Passkey als einziger Weg (Konten entstehen weiter über Google/Passwort), Attestation-Prüfung.
- **KI-Assistenten / MCP, nur lesen (v29, `routes/mcp.py`, `components/KiModal.jsx`):** Aufbau nach Haben. MCP-Server
  (Streamable HTTP, JSON-RPC 2.0, JSON-Antworten, kein SSE) unter **`POST /api/mcp`** (bewusst unter `/api`, damit
  Caddy ohne Änderung routet). Anmeldung nur per **Zugangs-Token** (`Authorization: Bearer tabmcp_…`): im Profil-Menü →
  „KI-Assistenten“ erzeugt der Inhaber ein Token (einmal sichtbar, gespeichert nur der SHA-256, max. 10, widerrufbar,
  `letzte_nutzung`), `/api/ki/tokens` ist `nur_inhaber`. Tokens gelten **nur** an `/api/mcp` (kein Cookie, keine andere
  Route akzeptiert sie) und Cookies gelten dort nicht; der Inhaber muss freigeschaltet bleiben (`ALLOWED_EMAILS`/
  `OPEN_SIGNUP`), Bremse 120 Anfragen/Minute je Token. **Nur lesen, dreifach:** nur lesende Werkzeuge
  (`gewerbe_liste`, `kennzahlen`, `euer_summenblatt`, `buchungen`, `rechnungen`, `wiederkehrende_rechnungen`,
  `uebersicht`, `anlagen`, `fristen`, `belege_eingang`, `kategorien`, alle mit `readOnlyHint`; `rechnungen` liefert neben dem
  rohen `faellig_am` auch `faellig_effektiv` (Altbestand ohne Ziel: Datum + 30 Tage) und `ueberfaellig` — ein leeres `faellig_am`
  hatte ein Assistent sonst als „keine Fälligkeit, also nie überfällig“ gelesen), die DB-Verbindung steht nach dem Token-Check auf
  `PRAGMA query_only = ON` (der Test versucht DELETE/UPDATE in einem eingeschleusten Werkzeug — scheitert, nichts ändert
  sich), und `ist_admin()` ist für Rolle `assistent` False. Die Werkzeuge rufen die vorhandenen Route-Funktionen direkt
  auf, also gilt `check_gewerbe` (fremdes Gewerbe → Werkzeugfehler „nicht gefunden“); Antworten werden bei 60.000
  Zeichen gekürzt (mit Hinweis), Buchungen mit `limit` (max. 200). **Neues Werkzeug** = Eintrag in `WERKZEUGE` + Handler,
  der nur liest. Nicht enthalten: Belegdateien, Mail-Zugang, Einstellungen, Bank-Umsätze, Kontakte. Datenschutz-Hinweis
  steht im Fenster: die Daten gehen an den Anbieter des Assistenten. Mit dem offiziellen MCP-Python-SDK (v2.3) als echtem
  Client gegen einen lokalen Server geprüft; mit Claude Code selbst nicht. OAuth für Claude.ai/Desktop: siehe nächsten
  Punkt. Schreiben nur als Vorschlag: siehe übernächsten Punkt. Nicht gebaut: direkt schreibende Werkzeuge, SSE/Server-Push, Token-Ablauf, Scopes je Gewerbe.
- **KI-Änderungsvorschläge (v31, `routes/vorschlaege.py`, Abschnitt „Vorschläge“ in `routes/mcp.py`, `pages/Uebersicht.jsx`):**
  Ein Assistent **ändert nichts selbst** — er legt einen Vorschlag ab, der Inhaber übernimmt oder verwirft ihn auf der Übersicht
  („Vorschläge von Claude“, Vorher/Nachher). **Stufe „Vorschläge machen“** je Zugangs-Token (`ki_token.vorschlaege`) bzw. OAuth-
  Zugriff (`oauth_grant.vorschlaege`, bei der Freigabe per Schalter, Standard **aus**), nachträglich umschaltbar
  (`PATCH /api/ki/tokens/{id}`, `/api/oauth/grants/{id}`, nur Inhaber); ohne Stufe stehen die drei Werkzeuge nicht einmal in
  `tools/list` und ein Aufruf liefert einen Werkzeugfehler. **Werkzeuge:** `abo_aenderung_vorschlagen` (Intervall, nächster Termin,
  pausieren, Positionen), `rechnungsentwurf_vorschlagen`, `rechnungsentwurf_aenderung_vorschlagen` (nur Status `entwurf`). Bewusst
  **nicht**: Buchen, Löschen, Versenden/Mahnen, Status, Zahlungen, Jahresabschluss, Änderung versendeter Rechnungen. **Prüfung wie in
  der Oberfläche:** dieselben Pydantic-Modelle (`AboPatch`, `RechnungIn`, `RechnungPatch`) und `check_gewerbe`; kein Effekt
  → Fehler; Datum höchstens 400 Tage zurück/60 voraus; max. 30 Positionen; Begründung auf 500 Zeichen gekürzt; höchstens 20 offene
  Vorschläge je Inhaber. **Einzige Schreibstelle des Assistenten:** `vorschlaege.anlegen()` über eine EIGENE Verbindung, die nur
  `ki_vorschlag` beschreibt — die Hauptverbindung bleibt `query_only`. **Übernehmen** (`POST /api/ki/vorschlaege/{id}/uebernehmen`, nur
  mit Anmeldung als Inhaber; ein Token darf nicht selbst bestätigen) ruft die vorhandenen Routen auf (`abos.update_abo`,
  `rechnungen.create_rechnung/update_rechnung`), also mit allen Prüfungen; `basis` (Stand des Ziels beim Anlegen) wird verglichen —
  hat sich das Ziel geändert → 409, der Vorschlag bleibt zum Verwerfen offen; sonstige Fehler → Status `fehlgeschlagen`. Im
  Änderungsprotokoll steht der Akteur als „<E-Mail> (KI-Vorschlag <id>, <Zugang>)“. Nicht gebaut: weitere Arten (Kontakt,
  Dauerbeleg, Buchung), Benachrichtigung bei neuem Vorschlag, automatisches Verfallen alter Vorschläge.
- **OAuth 2.1 für MCP — Claude.ai-Connectoren, Claude Desktop (v30, `routes/oauth.py`, `pages/OAuthFreigabe.jsx`,
  `frontend/nginx.conf`):** Tab ist Ressourcen- **und** Autorisierungsserver, nach der MCP-Spezifikation 2025-06-18.
  Ablauf: MCP-Aufruf ohne Token → 401 mit `WWW-Authenticate: Bearer resource_metadata=…` → Metadaten
  (`/.well-known/oauth-protected-resource[/…]` RFC 9728, `/.well-known/oauth-authorization-server[/…]` RFC 8414) →
  **dynamische Registrierung** `POST /api/oauth/register` (RFC 7591; nur öffentliche Clients, Weiterleitungsadressen https oder
  http auf localhost, max. 200 Clients, nie freigegebene Clients verfallen nach 2 Tagen) → `GET /api/oauth/authorize`
  (PKCE **S256 Pflicht**, `resource` muss die MCP-URL sein, ungültiger Client/Redirect → 400 ohne Weiterleitung, sonst Fehler
  per Redirect mit `iss`) → Weiterleitung zur **Freigabeseite `/oauth/freigabe`** (Inhaber muss angemeldet sein; wer es nicht
  ist, wird via `sessionStorage` `tab_oauth_zurueck` nach dem Login zurückgeführt, `Layout`) → `POST /api/oauth/freigabe`
  prüft alles noch einmal und gibt den Code aus (einmal, 5 min, nur SHA-256 gespeichert) → `POST /api/oauth/token`
  (`authorization_code` + `code_verifier`; `refresh_token` mit **Rotation**; Code-Wiederverwendung widerruft den daraus
  entstandenen Zugriff). Access-Token `tabo_…` 1 Stunde, Refresh `tabr_…` 30 Tage. Ein OAuth-Zugriff ist **dasselbe wie ein
  Zugangs-Token**: Rolle `assistent`, nur lesend, nur am MCP-Endpunkt, `query_only`, Inhaber muss freigeschaltet bleiben.
  Verwalten/Widerrufen: Profil-Menü → KI-Assistenten → „Verbundene Apps“ (`GET/DELETE /api/oauth/grants`). **nginx:** die
  `.well-known`-Adressen liegen am Wurzelpfad, der Frontend-Container reicht `/.well-known/oauth-*` ans Backend durch
  (Variable + `resolver 127.0.0.11`), alles andere unter `/.well-known/` ist 404 (kein index.html mit 200); Caddy bleibt
  unverändert. Aussteller/Ressource = `FRONTEND_URL` (`settings.public_origin`). Mit dem offiziellen MCP-Python-SDK (v2.3,
  `OAuthClientProvider`) als echtem Client den ganzen Fluss durchgespielt; mit Claude.ai selbst nicht. Nicht gebaut:
  Client-ID-Metadata-Dokumente, Client-Secrets/vertrauliche Clients, Scopes über „tab:lesen“, Token-Introspection/-Revocation-
  Endpunkt (Widerruf nur über die Oberfläche), CORS für den MCP-Endpunkt selbst (nur Metadaten/Register/Token).
- **Rechnungs-Abos (`routes/abos.py`, `services/abo.py`, Tabelle `rechnung_abo`):**
  wiederkehrende Rechnungen (monatlich/vierteljährlich/jährlich). Scheduler = asyncio-Task
  im `lifespan` (Start + alle 6 h): fällige Abos → echte Rechnung via
  `services/rechnungen.erstelle_rechnung` (gemeinsam mit der Route — Nummernlogik nur
  dort ändern). Platzhalter `{monat}` → Abrechnungsmonat MM/JJJJ; Leistungsdatum wird
  automatisch gesetzt; Ausstellungsdatum = Lauf-Tag. **Auto-Versand nur wenn** aktiviert +
  Empfänger-Mail + Absender-App-Passwort + Stichtag ≤ 7 Tage her (kein Mail-Schwall nach
  Server-Pause) — sonst bleibt die Rechnung als Entwurf. Verpasste Stichtage werden als
  Rechnungen nachgeholt. **Das Abo erstellt immer NEUE Rechnungen** — bestehende
  Entwürfe versendet es nie (Duplikat-Falle!). UI: Haken „Rechnung wiederholt sich"
  direkt im Anlege-Formular (Rechnung = erste Instanz, Abo startet eine Periode
  später, `lib/intervall.js` spiegelt naechster_termin); „Wiederholen…" an
  bestehenden Rechnungen ist ebenfalls eine Periode nach deren Datum vorbelegt.
  Abo-Liste mit Jetzt ausführen/Pausieren im Reiter „Wiederkehrend" der Rechnungen-Seite.
- **Zahlungen auf Rechnungen — Teilzahlungen, Skonto, Ausbuchen (`services/zahlungen.py`,
  `routes/rechnungen.py`, Tabelle `rechnung_zahlung`, v22):** Aufbau nach Haben (Zahlungen mindern den
  offenen Betrag, Skonto/Forderungsausfall buchen den Rest aus), auf die EÜR zugeschnitten:
  **Einnahme ist, was zufließt** — nur `art='zahlung'` ist Geld und (optional) mit einer
  Einnahme-Buchung verknüpft (`buchung_id`, Kategorie nach Steuerhinweis); `skonto` und `ausfall` sind
  Abzüge **ohne Buchung**. **offen = Summe − Zahlungen − Ausbuchungen**; Status `versendet`, bis nichts
  mehr offen ist, dann `bezahlt` (`aktualisiere_status`, `bezahlt_am` = letzte Zahlung). „Teilbezahlt“
  ist kein Status, sondern abgeleitet (`versendet` + `bezahlt_cent > 0`). `_row` liefert
  `bezahlt_cent/ausgebucht_cent/offen_cent/gebucht_cent/ungebucht_cent/zahlungen/skonto_*`.
  **Wege:** (1) „Zahlung erfassen…“ (`POST /rechnungen/{id}/zahlungen`: Datum, Betrag ≤ offen, optional
  gleich buchen, Rest als Skonto/Ausfall ausbuchen); (2) Status-Knopf „bezahlt“ (Entwürfe) legt eine
  ungebuchte Zahlung über den Rest an; (3) Bank-Zuordnung und „Als Einnahme buchen“ über
  `POST /buchungen` (`rechnung_id` + optional `zahlung_id`/`bank_umsatz_id`/`rest_ausbuchen`) —
  Betrag der Zahlung = Zahlungseingang auf dem Konto, Überzahlung zählt als bezahlt. Zahlung löschen
  nur ohne Buchung (erst die Buchung löschen). **Skonto** je Rechnung: Prozent (0,1–10) + Frist in
  Tagen ≤ Zahlungsziel, nur im Entwurf änderbar; steht auf dem PDF, in der E-Rechnung als
  `#SKONTO#TAGE=…#PROZENT=…#` (BR-DE-18) und löst im Bank-Vorschlag „Betrag mit Skonto, in der Frist“
  aus (Fristende → nächster Werktag, nur auf die unberührte Rechnung). **Mahnwesen und Bank-
  Vorschläge rechnen mit dem offenen Rest** (`offen_cent`); die Mahnung sagt, dass das Skonto entfallen
  ist. Migration v22 hat bezahlte Rechnungen als Zahlung über die Summe übernommen (mit ihrer
  Buchung). Nicht gebaut: Skonto in mehreren Stufen, Skonto an Abos, Zahlungen auf Entwürfe (nur der
  Status-Knopf), Gutschrift/Stornorechnung.
- **Angebote (`/rechnungen/angebote`, `pages/Angebote.jsx`, `routes/angebote.py`,
  `services/angebot_pdf.py`, v23):** Aufbau nach Haben (eigener Nummernkreis, optionale Positionen,
  Status, Umwandeln), schlank gehalten. Vierter Reiter in `RechnungenTabs`. **Nummer** `AN-{jahr}-{lauf:04d}`
  fortlaufend je Gewerbe + Jahr, vergeben beim Anlegen (Jahr aus dem Angebotsdatum; ein Datum in einem
  anderen Jahr lässt sich später nicht mehr setzen). **Positionen** `art` = `normal` (zählt zur
  Angebotssumme) | `optional` (Zusatzleistung, steht mit Preis im PDF, nicht in der Summe; mindestens
  eine normale nötig). **Status gespeichert:** `entwurf` → `versendet` → `angenommen` | `abgelehnt`;
  **abgeleitet** (nicht gespeichert): „Abgelaufen“ = versendet + `gueltig_bis` < heute, „Abgerechnet“ =
  `rechnung_id` gesetzt. `gueltig_bis` Standard = Datum + 30 Tage. **Inhalt nur im Entwurf änderbar,
  löschen nur Entwürfe** (versendetes: als abgelehnt markieren oder `POST /{id}/kopie` = neuer Entwurf mit
  Datum heute). **Senden** (`POST /{id}/senden`) setzt den Status vor dem PDF-Bau (das PDF trägt dann kein
  „ENTWURF“), bei Mail-Fehler Rollback. PDF: gleicher Briefbogen wie die Rechnung, kein GiroCode, keine
  ZUGFeRD-Einbettung (ein Angebot ist keine Rechnung). **Umwandeln** (`POST /{id}/rechnung`
  `{optional_ids, datum}`): nur aus `versendet`/`angenommen`, nur einmal (409) — erzeugt über
  `services/rechnungen.erstelle_rechnung` einen Rechnungsentwurf (normale + gewählte optionale Positionen,
  gleicher Empfänger/Steuerhinweis, Notiz „Bezug: Angebot …“, Standard-Zahlungsziel des Gewerbes), setzt das
  Angebot auf `angenommen` und `rechnung_id`; Rechnung (Entwurf) löschen → `ON DELETE SET NULL`, das Angebot
  ist wieder abrechenbar. Angebote sind **kein EÜR-Eintrag** und nicht jahresgesperrt; die Tabellen stehen im
  Änderungsprotokoll (`AUDIT_TABELLEN`). Nicht gebaut: Alternativpositionen, Zahlungsplan/Abschläge,
  Auftragsbestätigung, Lieferschein, Vorschau-PDF vor dem Speichern, Angebots-Abos.
- **Privatanteil bei Ausgaben (`buchung_position.privat_bp`, `services/privatanteil.py`, v24):** Position
  speichert den **gezahlten Betrag** (`betrag_cent`, brutto) und den privaten Anteil in **Basispunkten**
  (2000 = 20 %, 0–10000). **Nur der betriebliche Rest ist Betriebsausgabe** und geht in Summenblatt
  (`services/export.summenblatt`), Kennzahlen (`routes/meta.py`, `BETRIEBLICH_SQL`), Jahres-Check und
  „Summen je Kategorie“. Der private Teil ist in der EÜR **keine Entnahme** (die gibt es nur für Sach-/
  Nutzungsentnahmen, Z20/21) — es wird nichts zusätzlich gebucht. Rechenvorschrift: Privatanteil kaufmännisch
  gerundet, Rest betrieblich (`privat_cent`/`betrieblich_cent`, SQL und `lib/privat.js` rechnen gleich —
  beide ändern). Bewirtung: erst betrieblicher Teil, dann × 70 %. **Nur bei Ausgaben** (400 sonst, nicht bei
  AfA-Kategorien, die laufen über die AfA-Erfassung). Geld bleibt Zahlungsfluss: Bank-Zuordnung und Journal
  rechnen mit dem vollen Betrag. **Journal-CSV:** zwei Spalten am Ende (`Privatanteil %`, `Betrieblicher
  Betrag (EUR)`). **Siegel** (`services/abschluss.siegel`): `privat_bp` steckt nur im Hash, wenn gesetzt —
  so bleiben Siegel aus der Zeit vor v24 nachrechenbar. **UI:** „Auch privat genutzt“ je Ausgabe-Position im
  BuchungModal (Schalter + %, Live-Anzeige betrieblich/privat). **Gelernter Vorschlag:**
  `GET /api/buchungen/privatanteile?gewerbe_id=` = zuletzt verwendeter Privatanteil je Kategorie (nur > 0,
  der letzte Wert zählt auch, wenn er 0 war) — das Fenster schlägt ihn beim Wählen der Kategorie vor; keine
  Einstellung nötig. Nicht gebaut: fester Privatanteil je Kategorie als Einstellung, Privatanteil im
  CSV-Import, Aufteilung von Vorsteuer (Kleinunternehmer: gibt es nicht).
- **Dauerbelege (`/dauerbelege`, `pages/Dauerbelege.jsx`, `routes/dauerbelege.py`, `services/dauerbelege.py`,
  v24):** Aufbau nach Haben (Vorlage einmal, Termine fällig, Änderungen nur für künftige Termine,
  Pausieren/Beenden, **bucht nie von selbst**). Vorlage: Bezeichnung (wird die Buchungsbeschreibung),
  Ausgabe-Kategorie (nicht AfA, nicht `belegpflicht_extra`), Betrag brutto, Privatanteil, Rhythmus
  (monatlich/vierteljährlich/halbjährlich/jährlich), `naechste_am` = nächster **offener** Termin, `endet_am`,
  `aktiv`, Notiz. **Zeiger statt Termin-Tabelle:** „fällig“ = `naechste_am` ≤ heute (nachzuholende Termine
  werden nacheinander angezeigt, höchstens 60); `anker_tag` hält den Tag im Monat (31. → Monatsende und
  zurück; wer „Nächster Termin“ auf einen gekürzten Termin zurücksetzt, behält den Anker). **Termin buchen** =
  normales `POST /api/buchungen` mit `dauerbeleg_id` + `termin` (muss der nächste sein, sonst 409): die
  Buchung trägt beides, der Zeiger rückt weiter — gleicher Weg wie Rechnung und Bank (Jahres-Sperre gilt
  automatisch). **Überspringen** (mietfreier Monat) rückt den Zeiger ohne Buchung. **„Alle fälligen buchen“**
  (`POST /faellige-buchen`) bucht je Termin am Termintag; gesperrte Jahre landen in `fehler`, die Vorlage
  bleibt an dem Termin stehen. Je Vorlage und Termin höchstens eine Buchung (eindeutiger Index). **Löschen
  nur ohne Buchungen**, sonst pausieren oder beenden. **Fortsetzen** macht ab dem ersten Termin ≥ heute weiter
  (Pausen-Termine entfallen). **Bank:** `bank_match.dauerbeleg_treffer` schlägt für eine Abbuchung die Vorlage
  vor, deren nächster Termin passt (Betrag exakt 50 + Bezeichnung im Verwendungszweck 30 + Termin binnen 7
  Tagen 20, ab 70; Termin höchstens 10 Tage nach der Abbuchung) — „Termin buchen“ verbucht Termin und Umsatz
  zusammen. Badge „Dauerbelege“ in der Seitenleiste = fällige Termine (`GET /faellig`). Nicht gebaut:
  Vertragsdatei an jeder Buchung (Datei und Kontoauszug separat aufbewahren), mehrere Positionen je Vorlage,
  Auto-Buchen, Erinnerungs-Mails.
- **Fälligkeit + Mahnwesen (`routes/mahnwesen.py`, `services/mahnwesen.py`,
  `services/fristen.py`, `services/mahnung_pdf.py`, v17):** Aufbau und Abläufe nach **Haben**
  (github.com/firsttris/haben; Lars: „Aufbau nicht Farben" — bei neuen Seiten dort zuerst
  nachsehen, **AGPL: nur Ideen/Abläufe, keinen Code kopieren**). Rechnungen-Seite hat drei
  Reiter (`components/RechnungenTabs.jsx`): Alle Rechnungen · Wiederkehrend · Mahnwesen
  (`pages/Mahnwesen.jsx` Liste, `pages/MahnungNeu.jsx` Formular links + Forderungsaufstellung
  rechts, Route `/rechnungen/mahnwesen/:id`). **Fälligkeit** = Rechnungsdatum + Zahlungsziel
  (Standard je Gewerbe, 14 Tage; je Rechnung änderbar, nur im Entwurf), auf den nächsten
  Werktag verschoben (§ 193 BGB, nur **bundesweite** Feiertage, kein Bundesland); Ziel 0 =
  sofort ohne Verschiebung. `services/fristen.py` ↔ `lib/fristen.js` spiegeln sich — beide
  ändern. Steht auf PDF (Meta + „Zahlbar bis") und in der E-Rechnung (BT-9
  `DueDateDateTime`, BR-CO-25). **Überfällig** = Status `versendet` + Fälligkeit < heute;
  **Bestand ohne `faellig_am`** (vor v17) gilt als fällig bei Rechnungsdatum + 30 Tage
  (§ 286 Abs. 3 BGB, `effektive_faelligkeit`). Badge an „Rechnungen" in der Seitenleiste.
  **Mahnung:** Stufen 1 Zahlungserinnerung · 2 1. Mahnung · 3 Letzte Mahnung (nie rückwärts,
  nach Stufe 3 wiederholbar), Neue Frist (Gewerbe-Vorgabe 10 Tage), Mahngebühr je Stufe,
  **Verzugspauschale 40 €** (§ 288 Abs. 5 BGB, nur Geschäftskunden; eine Mahngebühr wird
  darauf angerechnet), **Verzugszinsen** = Basiszins + 9 (Geschäftskunde) / + 5 (Verbraucher)
  Punkte, taggenau ab dem Tag nach Fälligkeit, 365-Tage-Jahr, kaufmännisch gerundet — nur
  mit hinterlegtem Basiszinssatz (Gewerbe-Dialog, Knopf holt ihn von der Bundesbank-SDMX-API;
  im Januar/Juli oft noch der alte Satz → dann wird nichts übernommen). Tabelle `mahnung` ist
  ein **unveränderlicher Schnappschuss** (PDF wird bei jedem Abruf aus den Werten neu
  gebaut); löschen nur, solange nicht versendet. Frontend rechnet die Forderung live nach
  (`lib/mahnwesen.js`, gleiche Formel) — maßgeblich ist der Server. Mahnungen sind
  Schadensersatz/Zins, **kein Entgelt**: keine USt, keine automatische Buchung (Hinweis im
  Formular: als sonstige Betriebseinnahme buchen). Nicht abgedeckt: Mahnbescheid, Inkasso (Teilzahlungen und Skonto: siehe „Zahlungen auf Rechnungen“; Rechnung
  ist bezahlt oder nicht), Skonto, Mahnbescheid.
- **Bank-Import (`/bank`, `pages/Bank.jsx`, `routes/bank.py`, `services/bank_import.py` +
  `bank_match.py`, v21):** **Kein Bankabruf** — der Nutzer importiert die Datei seiner Bank:
  **CAMT.053** (XML) oder **CSV** (Trennzeichen/Kodierung/Kopfzeile werden erkannt, Vorspann wird
  übersprungen, IBAN aus dem Vorspann; Spalten werden aus den Überschriften geraten — DKB,
  Sparkasse-CSV, Soll/Haben getestet — und sind im Import-Dialog mit Vorschau änderbar, auch
  getrennte Spalten für Gegenpartei bei Eingang/Ausgang). XML mit DOCTYPE/ENTITY wird abgelehnt
  (XXE). Aufbau nach Haben (Konto aus der IBAN, Dubletten, Saldenprüfung, Zuordnungs-Vorschläge mit
  Begründung). **Dubletten:** Fingerprint aus Datum, Betrag, Gegenpartei, Zweck, Referenz + laufender
  Index je gleichem Umsatz — dieselbe/überlappende Datei darf beliebig oft importiert werden.
  Saldenprüfung nur bei CAMT (Anfangs-/Endsaldo). Fremdwährung und Vorgemerktes werden übersprungen.
  **Zugeordnet = `bank_umsatz.buchung_id IS NOT NULL`** (nicht gespeichert; Buchung löschen →
  Umsatz automatisch wieder offen), sonst `status` offen/ignoriert (mit Grund: privat, Umbuchung …).
  **Zuordnen läuft über das normale Buchungs-Fenster** (`BuchungModal`, Props `presetDatum`,
  `presetRichtung`, `umsatzId`): `POST /api/buchungen` mit `bank_umsatz_id` verknüpft den Umsatz in
  derselben Transaktion; zusammen mit `rechnung_id` wird die Rechnung `bezahlt` (am Umsatzdatum).
  So bleiben Kategorie-, Beleg- und Rechnungslogik an einer Stelle; die Jahres-Sperre gilt
  automatisch. **Vorschläge:** Eingang → offene (versendete) Rechnungen (Betrag exakt 50, Nummer im
  Zweck 40, Name 15, ab 40 Punkten; weicht der Betrag ab, gebucht wird der tatsächliche
  Zahlungseingang); Ausgang → Kategorie aus früheren Buchungen (`beleg_extract._kategorie_vorschlag`)
  und offene PDF/XML-Eingangs-Belege mit lesbarem Betrag (max. 25 geprüft, Bilder wegen OCR-Dauer
  nur per Auswahl). **Schon gebucht?** (`bank_match.buchung_treffer`,
  `POST /api/bank/umsaetze/{id}/zuordnen`): Umsatz einer **bestehenden** Buchung zuordnen statt eine zweite zu
  buchen (Summe gleich Umsatzbetrag 50, Datum binnen 14 Tagen 10/20, Beschreibung 30; ab 60; nur Buchungen ohne
  Umsatz und mit passender Richtung) — nötig, wenn ein Termin oder eine Rechnung vor dem Kontoauszug gebucht
  wurde. Die Tabellen stehen im Änderungsprotokoll (`AUDIT_TABELLEN`). Nicht gebaut:
  Splitbuchung eines Umsatzes, automatisches Buchen, mehrere Dateien auf
  einmal, gespeicherte Originaldateien.
- **Festschreibung / Jahresabschluss (`/abschluss`, `pages/Abschluss.jsx`, `routes/abschluss.py`,
  `services/audit.py` + `services/abschluss.py`, v20):** Aufbau nach Haben (Sperre + Protokoll als
  Datenbank-Trigger, Hash-Kette, Siegel, „Alles prüfen“, Prüfsummen im Archiv), eigenständig in
  SQLite umgesetzt. **Jahr abschließen** (erst nach Jahresende) sperrt je Gewerbe + Jahr per Trigger:
  Buchungen + Positionen, **Belege, die an einer Buchung des Jahres hängen** (Eingang bleibt frei),
  Fahrten und AfA (Anlegen/Löschen/Ändern von Kosten, Datum, Nutzungsdauer, Methode, Kategorie,
  wenn das Gut zur AfA des Jahres beiträgt; Bezeichnung und ein Abgang NACH dem Jahr bleiben
  änderbar). Verstoß → `RAISE` mit Präfix `JAHR_GESPERRT` → `main.py` macht daraus 409 mit
  lesbarer Meldung. Die Sperre greift **für jede Route automatisch** — neue Schreib-Routen brauchen
  nichts, solange sie auf `buchung`/`buchung_position`/`beleg`/`fahrt`/`afa_buchung` schreiben.
  **Rechnungen/Mahnungen sind nicht jahresgesperrt** (kein EÜR-Eintrag; „Als Einnahme buchen“ in ein
  gesperrtes Jahr scheitert an der Buchung). **Änderungsprotokoll** `audit_log`: Trigger auf
  `AUDIT_TABELLEN` (gewerbe, buchung, buchung_position, beleg, afa_buchung, fahrt, rechnung,
  rechnung_position, mahnung, jahr_abschluss) schreiben alt/neu als JSON; Akteur über die SQL-Funktion
  `tab_actor()` (`db.TabConnection.actor`: E-Mail aus dem Session-Cookie in `get_db`, in Hintergrund-
  läufen `system:<name>`). **Hash-Kette:** `row_hash = SHA-256(prev_hash ‖ Inhalt)`, vom Trigger
  gesetzt, Tabelle nur anhängbar. **Neue geschützte Tabelle:** in `AUDIT_TABELLEN` eintragen (Trigger
  folgen dem echten Schema, `ensure_triggers` gleicht bei jedem Start ab — auch nach Rebuild-
  Migrationen). **Folgen:** Schreiben außerhalb der App (z. B. `sqlite3`-CLI) scheitert absichtlich
  („no such function: tab_actor“), siehe Mandantentrennung unten; Beleg löschen = erst DB, dann
  Datei (sonst ginge bei abgelehntem Löschen die Datei verloren). **Siegel** beim Abschluss: SHA-256
  über Buchungen+Positionen, Belege (mit SHA-256 der Datei), berechnete AfA und Fahrten — nur, was die
  Sperre schützt (sonst bräche das Siegel bei erlaubten Änderungen). „Alles prüfen“ rechnet Kette,
  Siegel und das Vorhandensein aller Trigger nach. **Wieder öffnen** nur mit Begründung (im
  Protokoll), danach neues Siegel beim erneuten Schließen. Das Jahres-ZIP enthält jetzt
  `pruefsummen.sha256`, `protokoll/aenderungsprotokoll.csv`, `protokoll/pruefwert.txt` (Kopf der
  Kette + Siegel, zum Aufbewahren außerhalb des Servers) und `LIESMICH.txt`. **Grenzen, nicht
  versprechen:** keine GoBD-Zertifizierung; wer die DB direkt ändert (Trigger droppen), umgeht die
  Sperre — Kette/Siegel machen es sichtbar, verhindern es nicht; Zeit vor v20 ist nicht protokolliert
  (Genesis-Eintrag).
- **Fristen (`/fristen`, `pages/Fristen.jsx`, `routes/fristen.py`, `services/steuerfristen.py`,
  v19):** Aufbau nach Haben (Überfällig · Nächste 30 Tage · Später · Kalender-Abo · Erledigt).
  Nur Steuertermine, die für Tab-Nutzer gelten: **Einkommensteuererklärung mit Anlage EÜR** je
  Jahr ab 2024 (31.7. des Folgejahres, auf Werktag verschoben, ohne Steuerberatung; erscheint für
  Jahre mit Buchungen/Rechnungen eines eigenen Gewerbes) und optional (Schalter, je Login)
  **ESt-Vorauszahlungen** 10.3./6./9./12. als reiner Hinweis. **Keine USt-Voranmeldung**
  (Kleinunternehmer; Regelbesteuerung gibt es in Tab nicht). Erledigt hakt der Nutzer von Hand ab
  (`frist_erledigt`, je Login) — Tab überträgt nichts ans Finanzamt. Zähler an „Fristen" in der
  Seitenleiste = offene Erklärungen, überfällig oder in ≤ 14 Tagen. **Kalender-Abo:** geheimer
  Link `GET /api/fristen/kalender/{token}.ics` (ohne Login, nur SHA-256-Hash gespeichert, Link nur
  beim Erzeugen sichtbar, neuer Link macht den alten ungültig); ganztägige Termine mit Erinnerung
  3 Tage vorher + am Morgen (je 9 Uhr), Erledigtes fehlt im Feed. Nicht gebaut: E-Mail-Erinnerungen,
  eigene Fristen (z. B. Einspruch), Fristen mit Steuerberatung.
- **GiroCode (`services/girocode.py`, v18):** EPC-QR (Version 002, UTF-8, Fehlerkorrektur M,
  Bibliothek `segno`, als Vektor ins PDF gezeichnet) neben der Zahlungsinfo der Rechnung und der
  Zahlungsaufforderung der Mahnung (Betrag = Rechnungssumme bzw. Mahn-Gesamtbetrag,
  Verwendungszweck „Rechnung {nr}"). **Nie blockierend:** ohne IBAN, mit ungültiger IBAN
  (Prüfziffer mod 97), Betrag 0 oder leerem Namen kommt das PDF ohne Code; bezahlte/stornierte
  Rechnungen und der Mahn-Entwurf (Platzhalter) bekommen keinen. Empfängername =
  `gewerbe.kontoinhaber`, sonst erste Zeile der Anschrift (`absender_name` — der interne
  Gewerbe-Name ist oft nur ein Etikett wie „Makler"); Banken prüfen ihn bei der
  Empfängerüberprüfung. Ausdrücklich gesetzter Kontoinhaber steht auch im PDF und als
  `AccountName` (BT-85) in der E-Rechnung. Die Positionstabelle bricht Zeilen nur als Ganzes um.
- **PDF-Texte (`rechnung_pdf.latin1`):** Core-Font Helvetica ist Latin-1 — jeder
  Nutzertext (Position, Notiz, Anschrift, Fußzeile, Mahntexte) läuft durch `latin1()`
  (Gedankenstrich/Anführungszeichen/€ werden ersetzt), sonst bricht die PDF-Erzeugung ab.
  Neue PDF-Felder immer damit umhüllen.
- **Beleg-Erkennung (`services/beleg_extract.py`, GET `/belege/{id}/vorschlag`):**
  3-stufig lokal — (1) E-Rechnung: XRechnung-XML/ZUGFeRD-XML-im-PDF exakt geparst
  (tolerant über local-names), (2) PDF-Textebene via PyMuPDF + Heuristiken
  (Betrag-Keywords, Datumsmuster, erste Zeile = Lieferant), (3) Foto/Scan via
  Tesseract `deu` (im Dockerfile installiert; fehlt das Binary, degradiert alles
  still). Kategorie-Vorschlag: erst lernend (frühere Buchung mit Lieferant-Token
  in der Beschreibung), dann `KEYWORD_KATEGORIEN`. **Immer nur Vorschlag** —
  BuchungModal befüllt beim Verbuchen leere Felder vor und zeigt einen Prüf-Hinweis;
  der Endpoint darf das Verbuchen nie blockieren (Fehler → leerer Vorschlag).
  **Richtung (Einnahme/Ausgabe):** der Vorschlag liefert `richtung` + `richtung_erkannt`
  (Score aus `EINNAHME_SIGNALE`/`AUSGABE_SIGNALE`, eigener Gewerbename als Aussteller,
  sonst gelernte Kategorie; ohne Signal Default Ausgabe). BuchungModal hat dafür den
  Ausgabe/Einnahme-Umschalter und zeigt nur Kategorien dieser Richtung (`kategorie.typ`);
  Alt-Buchungen mit gemischten Positionen = alle Kategorien. Wechsel setzt nicht
  passende Kategorien zurück.
  XML-Upload übernimmt die Fälligkeit automatisch in `beleg.faellig_am`.
- **Beleg-Zugänge außer Upload:** (1) **Mail-Import** (`services/mail_import.py`,
  Scheduler alle 10 min): holt per IMAP (imap.gmail.com, gleiches App-Passwort)
  Mails an die eigene **+tab-Adresse** ab (letzte 14 Tage, `readonly` — Postfach
  wird nie verändert), speichert Anhänge via `services/beleg_store.speichere_beleg`
  in den Eingang. Guards: nur Absender aus der Allowlist, Dedup über Message-ID
  (`mail_import`). Einstellungen je Login: PUT `/api/einstellungen/mail/import`
  (Toggle + Ziel-Gewerbe), UI im MailSetupModal. (2) **PWA-Share-Target**
  (`public/manifest.webmanifest` + `public/sw.js`): Teilen vom Handy → SW fängt
  POST `/share-target` ab → `/api/belege/share` (Ziel = Import-Gewerbe, sonst
  erstes aktives) → Redirect `?geteilt=ok|fehler` (Toast in Buchungen). SW macht
  bewusst KEIN Caching. Android/Chrome only — iOS kann kein Share-Target (Mail-Weg).
  Datei-Validierung/XML-Fälligkeit zentral in `beleg_store` (Upload nutzt es auch).
- **Kontakte (`routes/kontakte.py`, Tabelle `kontakt`):** Rechnungsempfänger je Gewerbe,
  Name case-insensitiv eindeutig. **Füllen sich automatisch**: Rechnung/Abo anlegen
  upsertet den Empfänger (`upsert_kontakt` — nur nicht-leere Felder überschreiben).
  UI: „Aus Kontakten übernehmen"-Picker in Rechnungs- und Abo-Modal, Pflege über
  `KontakteModal` (Button „Kontakte" auf der Rechnungen-Seite).
- **Beleg verschieben:** offene Eingangs-Belege können per PATCH (`gewerbe_id`) in ein
  anderes eigenes Gewerbe wandern (UI: „Verschieben…"-Dropdown im Eingang bei >1 Gewerbe).
- **Mail-Konto individuell je Login (`routes/einstellungen.py`, `services/mailer.py`, v13):**
  Provider **'google'** (App-Passwort, smtp/imap.gmail.com) oder **'custom'** (eigener
  Mail-Server, z. B. All-Inkl: Host/Port/Benutzer/Absender frei, Port 587 STARTTLS oder
  465 SSL — Hetzner blockt nur 25/465-ausgehend teils, 587+993 sind offen, live geprüft).
  `lade_konto()` löst alles inkl. Defaults auf; From: = `absender_email` (custom) bzw.
  Login-Adresse. Import-Ziel = `import_adresse` oder +tab-Variante des Absenders
  (`mail_import.import_ziel`). Passwort Fernet-verschlüsselt (Schlüssel aus JWT_SECRET),
  beim Speichern SMTP-Login live verifiziert. **JWT_SECRET ändern macht gespeicherte
  Passwörter unlesbar** (Nutzer hinterlegen neu — Meldung kommt automatisch).
  Faustregel (steht im Wizard): eigene Absender-Domain pro Firma → eigener Login.
- **Offene Registrierung (`OPEN_SIGNUP=true` in .env):** jedes Google-Konto darf sich
  anmelden — UND (v14) **E-Mail + Passwort ohne Google**: `nutzer`-Tabelle, scrypt-Hash
  (stdlib), 6-stellige Verifizierungs-/Reset-Codes über den **System-Mail-Absender**
  (`SYSTEM_SMTP_*` in .env; ohne diese Werte ist der Passwort-Weg automatisch aus,
  GET `/api/auth/methoden` steuert das Login-Formular). Brute-Force-Bremse in
  `auth/local.py` (5 Fehlversuche → 15 min, in-memory). OAuth-Callback verlangt
  `email_verified` (wichtig für Google-Konten mit externer Adresse). Die Allowlist bleibt aktiv als **Admin-Liste** (`ALLOWED_EMAILS` → `ist_admin`,
  Backup-Zugriff, Sicht auf herrenlose Gewerbe) und als Vertrauenskreis beim Mail-Import.
  Schutz gegen Missbrauch: Beleg-Speicher-**Quota je Nutzer** (`QUOTA_MB`, Default 500,
  geprüft in `beleg_store`), Upload-Größenlimit, Mail-Import nur von eigenen/vertrauten
  Absendern. Voraussetzung (manuell in Google Cloud): OAuth-Consent-Screen auf
  „In production", sonst blockt Google fremde Logins.
- **Mandantentrennung (v12):** `gewerbe.owner_email` — **jede Route** prüft Zugriff über
  `auth/deps.check_gewerbe` (fremd → 404, keine Existenz verraten). `owner_email NULL` =
  herrenloser Alt-Bestand: **nur für Admins sichtbar** (zum Zuordnen per `UPDATE gewerbe SET
  owner_email=…` — **nicht** mit der `sqlite3`-Kommandozeile, die scheitert seit v20 an den
  Protokoll-Triggern; stattdessen `docker exec tab-backend python -c "from app.db import _connect;
  c=_connect(actor='admin'); c.execute('UPDATE gewerbe SET owner_email=? WHERE id=?', ('…', 1));
  c.commit()"`). Neue Gewerbe gehören dem Ersteller.
  Row-Level-Objekte (Buchung/Beleg/Rechnung/Abo/Fahrt/AfA/Kontakt) erben über ihr Gewerbe.
  **Backup (`/api/export/backup.zip`) nur für Admins** = explizite `ALLOWED_EMAILS`-Einträge
  (`ist_admin`), Domain-Nutzer nicht. Bei NEUEN Routen mit `gewerbe_id`/Objekt-IDs IMMER
  `check_gewerbe` einbauen. Ein Nutzer = eine E-Mail (Gmail vs. Workspace nicht mischen).

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
  Vorsteuer, Zeilen 15/17 + Vorsteuer/USt-Zahllast und der Export dafür fehlen. Braucht eine eigene Mapping-Spec
  (analog `EUER_KATEGORIEN.md`) bevor man Steuer-Zeilen festlegt — nicht raten.
- Weiterhin außen vor: Multi-User/Mandant, Bankabruf, ELSTER-Direktversand, USt-Voranmeldung.
