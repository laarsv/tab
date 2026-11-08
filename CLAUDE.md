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
(`rechnung.zahlungsziel_tage`/`faellig_am`, Gewerbe-Einstellungen `zahlungsziel_tage`/`mahn_frist_tage`/`mahn_gebuehr_{1,2,3}_cent`/`basiszinssatz_bp`, Tabelle `mahnung`), v18 = `gewerbe.kontoinhaber`, v19 = `frist_einstellung` + `frist_erledigt` (Fristen-Seite), v20 = `audit_log` + `jahr_abschluss` (Festschreibung; die Trigger legt `services/audit.ensure_triggers()` bei jedem Start an), v21 = `bankkonto` + `bank_import` + `bank_umsatz` (Bank-Import), v22 = `rechnung_zahlung` + `rechnung.skonto_bp`/`skonto_tage` (Teilzahlungen, Skonto), v23 = `angebot` + `angebot_position` (Angebote).

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
- **GWG:** weicher Hinweis im UI (800 € netto ≈ 952 € brutto), keine harte Prüfung. Weitere
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
  mit Buchungen/Rechnungen/Check/Mehr). Inhalt: Wortmarke, „Neue Buchung" + Upload-Icon,
  Gewerbe/Jahr-Kapseln, **„Jetzt"-Zeile = Beleg-Eingang** (nur wenn etwas wartet), Nav
  (Buchungen · Rechnungen · Jahres-Check mit Badge · Abschreibungen), „Weitere" (Export, Gewerbe,
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
  nur per Auswahl). Die Tabellen stehen im Änderungsprotokoll (`AUDIT_TABELLEN`). Nicht gebaut:
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
