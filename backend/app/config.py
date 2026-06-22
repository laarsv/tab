"""Konfiguration aus Umgebungsvariablen (.env). Single-User, keine DB-User-Tabelle."""
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

    # Single-User-Login
    ADMIN_USERNAME: str = "lars"
    # bcrypt-Hash des Passworts — erzeugen mit scripts/hash_password.py
    ADMIN_PASSWORD_HASH: str = ""

    # JWT (Bearer-Token im Authorization-Header)
    JWT_SECRET: str = "change-me-openssl-rand-hex-32"
    JWT_TTL_DAYS: int = 30

    # CORS: leer = same-origin (Frontend ruft https://tab.vrwb.de/api → kein CORS nötig).
    # Komma-getrennte Origin-Liste nur falls Frontend auf anderer Origin läuft.
    CORS_ORIGINS: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
