"""Konfiguration aus Umgebungsvariablen (.env).

Auth: Google OAuth (wie die anderen Tools). Single-User über E-Mail-Allowlist,
Session als HttpOnly-JWT-Cookie. Keine User-DB.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite-Datei (im Prod-Bind-Mount /opt/appdata/tab/data → /app/data)
    DB_PATH: str = "/app/data/tab.db"

    # Beleg-Datei-Uploads (im Prod-Bind-Mount /opt/appdata/tab/uploads → /app/uploads)
    UPLOAD_ROOT: str = "/app/uploads"
    MAX_UPLOAD_MB: int = 10

    # ── Google OAuth ──────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_REDIRECT_URI: str = "https://tab.vrwb.de/api/auth/callback"
    # Anmeldung erlaubt für: diese exakten E-Mails (Komma-getrennt) ODER ...
    ALLOWED_EMAILS: str = ""
    # ... jede Adresse dieser Domains (Komma-getrennt, z. B. "example.com").
    ALLOWED_EMAIL_DOMAINS: str = ""
    # Wohin nach Login/Logout zurück (Frontend-Origin).
    FRONTEND_URL: str = "https://tab.vrwb.de"

    # ── Session (JWT im Cookie) + OAuth-State-Middleware ──────────────────────
    JWT_SECRET: str = "change-me-openssl-rand-hex-32"
    JWT_TTL_DAYS: int = 30
    SESSION_SECRET: str = "change-me-openssl-rand-hex-32"  # Starlette SessionMiddleware (OAuth-State)
    COOKIE_NAME: str = "tab_session"
    COOKIE_SECURE: bool = True
    COOKIE_DOMAIN: str | None = None

    # CORS: leer = same-origin (Frontend + API auf https://tab.vrwb.de → kein CORS).
    CORS_ORIGINS: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_emails_list(self) -> list[str]:
        return [e.strip().lower() for e in self.ALLOWED_EMAILS.split(",") if e.strip()]

    @property
    def allowed_email_domains_list(self) -> list[str]:
        return [
            d.strip().lower().lstrip("@")
            for d in self.ALLOWED_EMAIL_DOMAINS.split(",")
            if d.strip()
        ]

    def is_email_allowed(self, email: str) -> bool:
        e = (email or "").strip().lower()
        if not e or "@" not in e:
            return False
        if e in self.allowed_emails_list:
            return True
        return e.split("@")[-1] in self.allowed_email_domains_list


settings = Settings()
