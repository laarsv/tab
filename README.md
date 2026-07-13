# Tab

Schlankes Buchhaltungstool für Einzelunternehmer mit **Kleinunternehmerregelung (§19 UStG)**.
Belege erfassen, Kategorien zuordnen, am Jahresende eine **EÜR als Summenblatt pro
Anlage-EÜR-Zeile** + **Beleg-Journal (CSV)** exportieren — zum Übertragen ins
Steuerprogramm/ELSTER. **Kein** ELSTER-Direktversand, **kein** Bankabruf.

- **Multi-Gewerbe**: eine EÜR pro Gewerbe (z. B. Makler + App).
- **Single-User** (Phase 1), JWT-Bearer-Login.
- Mapping **jahres-versioniert** (2025 verifiziert, 2026 vorläufig).

> Tab ist eine technische Hilfe, **keine Steuerberatung**.

## Stack

- **Backend:** FastAPI + SQLite (eine Datei, kein DB-Container). Migrationen als simple
  Liste (`app/migrations.py`), idempotenter Seed (`app/seed.py`). Kein Alembic.
- **Frontend:** React 18 + Vite + Tailwind (JS). UI strikt gemäß `DESIGN.md`
  (Mint/Ink/Paper, Roboto self-hosted via `@fontsource`, Custom-Dropdowns).
- **Fachliche Quelle:** `EUER_KATEGORIEN.md` (Kategorien, Zeilen-Mapping, Sonderfälle).

## Lokale Entwicklung

```bash
cp .env.example .env
# GOOGLE_CLIENT_ID/-SECRET in .env eintragen (siehe „Einmalig einrichten“ unten)
openssl rand -hex 32                        # JWT_SECRET + SESSION_SECRET in .env eintragen

docker compose -f docker-compose.dev.yml up --build
# Frontend: http://localhost:5173   Backend: http://localhost:8000
```

Ohne Docker:

```bash
# Backend
cd backend && python3.12 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
DB_PATH=./tab.db uvicorn app.main:app --reload

# Frontend (zweites Terminal)
cd frontend && npm install && npm run dev
```

## Auth (Google OAuth)

Login läuft über **Google OAuth** (wie die anderen Tools); Session als HttpOnly-Cookie.
Single-User über E-Mail-Allowlist — nur `ALLOWED_EMAILS` dürfen rein.

Einmalig einrichten:
1. **Google Cloud Console** → OAuth-2.0-Client, Typ „Web application".
2. **Autorisierte Redirect-URI:** `https://tab.vrwb.de/api/auth/callback`.
3. Client-ID/-Secret in die `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).
4. `ALLOWED_EMAILS=du@example.com`, `JWT_SECRET` + `SESSION_SECRET` (`openssl rand -hex 32`).

## Deployment (Hetzner, Docker-Compose)

Siehe `scripts/deploy.sh` und `caddy.snippet`.

```bash
# auf dem Server, einmalig:
mkdir -p /opt/appdata/tab/data /opt/appdata/tab/uploads
git clone <repo> tab && cd tab
cp .env.example .env && nano .env           # Google-OAuth + Secrets setzen

./scripts/deploy.sh                          # build + up -d + Healthcheck
# caddy.snippet an /opt/appdata/caddy/Caddyfile anhängen und Caddy reloaden
```

- Container heißen explizit **`tab-backend`** und **`tab-frontend`**, hängen am externen
  Docker-Netz **`proxy`**, **ohne** Host-Port-Mapping.
- SQLite-Datei liegt im Bind-Mount **`/opt/appdata/tab/data`** → ins Server-Backup aufnehmen.
- Caddy routet `tab.vrwb.de`: `/api` → `tab-backend:8000`, Rest → `tab-frontend:80`.
- Das Frontend wird mit gebaketem `VITE_API_BASE_URL=https://tab.vrwb.de`
  (`frontend/.env.production`, getrackt) gebaut → same-origin, kein CORS.

## Mapping jährlich pflegen

Die Zeilennummern der Anlage EÜR verschieben sich pro Jahr. Mapping liegt jahres-versioniert
in `backend/app/seed.py` (`ZEILEN`, `MAPPING`, `JAHRE`). Der Seed ist **Upsert** — eine
Korrektur deployt man, indem man die Daten dort anpasst und neu ausrollt; Buchungen bleiben
unberührt (sie speichern die Kategorie, nicht die Zeile).

- **2025**: verifiziert (ELSTER-Anleitung 08/2025).
- **2026**: vorläufige Kopie von 2025 — vor Steuersaison gegen den Vordruck 2026 abgleichen.
- ⚠ Die Kategorien für laufende Kosten (Telekommunikation, Versicherungen, Wartung,
  Beratung, Fortbildung, Werbung, Leasing bewegl. WG) zeigen vorläufig auf **Zeile 60**
  („übrige unbeschränkt abziehbar"). Das ist gewinnneutral; finale Zeile (43–54) beim
  Vordruck-Abgleich setzen.

## API (Kurzüberblick)

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/auth/login` · `/callback` · `/me` · POST `/logout` | Google-OAuth-Login (Cookie-Session) |
| GET | `/api/gewerbe` · POST · PATCH `/{id}` | Gewerbe-Verwaltung |
| GET | `/api/kategorien?jahr=` | Kategorien inkl. aufgelöster Zeile |
| GET/POST/PATCH/DELETE | `/api/buchungen` | Buchungen CRUD |
| GET/POST/PATCH/DELETE | `/api/afa` | AfA-Wirtschaftsgüter CRUD |
| GET | `/api/kennzahlen?gewerbe_id=&jahr=` | Summen + KU-Grenz-Guard |
| GET | `/api/export/summenblatt` | Summenblatt (JSON) |
| GET | `/api/export/summenblatt.csv` · `/api/export/journal.csv` | CSV-Downloads |
