# CLAUDE.md — Tab

Arbeitsanweisungen für Claude Code in diesem Repo. Kurz halten, beim Ändern aktuell halten.

## Was ist Tab

Schlanke EÜR-Buchhaltung für Einzelunternehmer mit **Kleinunternehmerregelung (§19 UStG)**.
Belege erfassen → Kategorien → am Jahresende **EÜR-Summenblatt pro Anlage-EÜR-Zeile** +
**Beleg-Journal (CSV)** exportieren. Kein ELSTER-Direktversand, kein Bankabruf, nur manuell
erfasste Belege. Multi-Gewerbe (eine EÜR pro Gewerbe). Single-User (Phase 1).
**Keine Steuerberatung.**

## Verbindliche Quellen

- **`DESIGN.md`** — **verbindliche Marken-/Farbnorm: VRWB CI v1.0, Royal Blue.** Tokens
  `royal` (`#2947c9`/soft `#aeb9ee`), `ink` `#161a24`, `paper`. **Kontrastregel (wichtig, anders
  als bei Mint):** Royal ist ein *dunkler* Akzent → Text auf **gefüllten** Royal-Flächen ist
  **weiß (`paper`)** (`.btn-primary`, Badges); Royal als *Textfarbe* auf Weiß ist ok (Nav aktiv,
  Eyebrow, Links). **Tool-Marke** (CI-Konvention, Details + Quelle in DESIGN.md §1b;
  zentral in `components/Wordmark.jsx` — nie inline nachbauen): **App-Header =
  `SignaturLockup`** (Signatur als Inline-SVG in Royal + Haarlinie + Standalone
  `vrwb_tab`, präferiert lt. CI); **Login/Footer/Titel = Standalone `vrwb_tab`** (`vrwb` Roboto 900
  −4,5 %, `_tab` Royal, Toolname Roboto Mono 500 0,83× −1 %, immer klein; auf Ink `_tab`
  Royal Soft). Favicon `t_` auf Royal (`public/favicon.svg`). Roboto + Roboto Mono
  self-hosted, kein Google-CDN. `theme-color = #2947c9`.
- **`DESIGN.shared.md`** — Dichte-/Komponenten-Konventionen (Dichte v2): 44 px Touch **mobil**,
  Desktop kompakt (~32–36 px) — Tipp-Felder `py-2.5 text-base` auf Base, ab `sm:` `py-1.5 text-sm`
  (iOS-Zoom-Schutz nie brechen). `.field-label` (dezent), `.eyebrow`, Formular-Grids `gap-x-5 gap-y-2`,
  Ghost-Select für Inline-Werte. Zentrale Klassen in `src/index.css`
  (`.btn/.btn-sm/.input/.field-label/.eyebrow/.card`), Select in `components/Dropdown.jsx`
  (`variant="ghost"`). **Diese Muster gelten weiter — nur die Palette ist Royal statt Mint** (DESIGN.md gewinnt bei Farbe/Kontrast).
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
v11 = Mail-Import (`user_mail.import_*` + Dedup-Tabelle `mail_import`).

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
  Jahres-AfA fließt in Zeile 33, wird **berechnet, nicht gespeichert**. **Abgang**
  (`abgang_datum`): AfA endet mit dem Abgangsmonat; `restbuchwert_cent` wird berechnet und im
  UI als Hinweis gezeigt (manuell als Buchung Zeile 38 erfassen, Erlös Zeile 19).
- **GWG:** weicher Hinweis im UI (800 € netto ≈ 952 € brutto), keine harte Prüfung. Weitere
  Soft-Hinweise: Geschenke > 50 € (Freigrenze), Homeoffice > 1.260 €/Jahr.
- **Rechner-Helfer (`BuchungModal.jsx`, `CALCULATORS`):** Fahrtkosten (km × 0,30 €),
  Entfernungspauschale (Tage × km, 0,30/0,38 ab km 21), Homeoffice (Tage × 6 €),
  Verpflegungsmehraufwand (28/14 €), 1 %-Regelung (Listenpreis × Antriebs-Satz 1/0,5/0,25
  für Verbrenner/Hybrid/E-Auto, auf 100 € abgerundet, × Monate; Select-Feldtyp im
  CALCULATORS-Framework). Sie **füllen nur das Betragsfeld** — das Betragsfeld bleibt
  Quelle der Wahrheit, Backend speichert nur den Betrag (Edit-sicher).
- **1 %-Regelung (Betriebs-Kfz), bewusst schlank:** Entnahme = Einnahme-Kategorie
  `kfz_privatnutzung` (Zeile 20, ⚠), Kosten = `kfz_kosten` (vorläufig Zeile 60, final 68–70).
  NICHT abgedeckt: 0,03 %-Wege-Kürzung (Z72), Kostendeckelung, Fahrtenbuch. Die Entnahme
  zählt nicht in `ku_umsatz` (Vereinfachung, siehe EUER_KATEGORIEN.md §4.6).
- **KU-Grenz-Guard (`/api/kennzahlen`):** Grenzvergleich (25.000/100.000 €) läuft über
  `ku_umsatz_cent` = nur Kategorie `einnahme_ku` — steuerfreie Courtage (§4 Nr. 11) und
  Anlagenverkäufe bleiben nach §19 Abs. 2 UStG außer Ansatz.
- **Mapping jahres-versioniert:** 2025 verifiziert, 2026 vorläufig (`vorlaeufig=1`). Fehlt ein
  Mapping fürs Jahr **oder für eine bebuchte Kategorie** → `MappingMissingError` → 400 mit
  klarer Meldung (kein stilles Weglassen von Beträgen).
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
  Login automatisch (localStorage `tab_news_gesehen`), sonst über Profil-Menü „Neuigkeiten".
- **Einrichtung & Hilfe (`/einrichtung`, `pages/Einrichtung.jsx`):** geführter 5-Schritte-
  Wizard (Gewerbe/Absender, App-Passwort, Mail-Import, PWA aufs Handy, erste Buchungen) —
  Status wo möglich automatisch aus echten Daten, PWA per Haken (localStorage
  `tab_setup_haken`). Detail-Anleitungen für App-Passwort/+tab-Adresse/PWA leben HIER
  (nicht duplizieren). `openMailSetup` kommt aus dem Layout-Context.
- **Navigation (Einsteiger-IA):** Nav = Buchungen · Jahres-Check (Badge = offene Themen) ·
  Abschreibungen; Export/Gewerbe/Einrichtung/Abmelden hinter der **Profil-Bubble** (Initialen, rechts).
  Der Beleg-Eingang ist **in die Buchungen-Seite integriert** (Karte „Beleg-Eingang" mit
  Upload, Liste, „Jetzt abarbeiten"); `/eingang` redirectet auf `/buchungen`.
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
  km-Pauschale (Privatwagen, Zeile 71) — Datum/Ziel/Anlass/km, Summe × 0,30 € per Klick als
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
- **Rechnungs-Abos (`routes/abos.py`, `services/abo.py`, Tabelle `rechnung_abo`):**
  wiederkehrende Rechnungen (monatlich/vierteljährlich/jährlich). Scheduler = asyncio-Task
  im `lifespan` (Start + alle 6 h): fällige Abos → echte Rechnung via
  `services/rechnungen.erstelle_rechnung` (gemeinsam mit der Route — Nummernlogik nur
  dort ändern). Platzhalter `{monat}` → Abrechnungsmonat MM/JJJJ; Leistungsdatum wird
  automatisch gesetzt; Ausstellungsdatum = Lauf-Tag. **Auto-Versand nur wenn** aktiviert +
  Empfänger-Mail + Absender-App-Passwort + Stichtag ≤ 7 Tage her (kein Mail-Schwall nach
  Server-Pause) — sonst bleibt die Rechnung als Entwurf. Verpasste Stichtage werden als
  Rechnungen nachgeholt. UI: „Wiederholen…" an jeder Rechnung erstellt das Abo vorbefüllt;
  Abo-Liste mit Jetzt ausführen/Pausieren oben auf der Rechnungen-Seite.
- **Beleg-Erkennung (`services/beleg_extract.py`, GET `/belege/{id}/vorschlag`):**
  3-stufig lokal — (1) E-Rechnung: XRechnung-XML/ZUGFeRD-XML-im-PDF exakt geparst
  (tolerant über local-names), (2) PDF-Textebene via PyMuPDF + Heuristiken
  (Betrag-Keywords, Datumsmuster, erste Zeile = Lieferant), (3) Foto/Scan via
  Tesseract `deu` (im Dockerfile installiert; fehlt das Binary, degradiert alles
  still). Kategorie-Vorschlag: erst lernend (frühere Buchung mit Lieferant-Token
  in der Beschreibung), dann `KEYWORD_KATEGORIEN`. **Immer nur Vorschlag** —
  BuchungModal befüllt beim Verbuchen leere Felder vor und zeigt einen Prüf-Hinweis;
  der Endpoint darf das Verbuchen nie blockieren (Fehler → leerer Vorschlag).
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
  herrenloser Alt-Bestand: **nur für Admins sichtbar** (zum Zuordnen via
  `UPDATE gewerbe SET owner_email=…`). Neue Gewerbe gehören dem Ersteller.
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
  Vorsteuer, Zeilen 15/17/57/58 und der Export dafür fehlen. Braucht eine eigene Mapping-Spec
  (analog `EUER_KATEGORIEN.md`) bevor man Steuer-Zeilen festlegt — nicht raten.
- Weiterhin außen vor: Multi-User/Mandant, Bankabruf, ELSTER-Direktversand, USt-Voranmeldung.
