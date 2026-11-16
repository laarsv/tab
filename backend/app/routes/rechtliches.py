"""Öffentliche Angaben für die Datenschutzseite (ohne Anmeldung). Name, Anschrift und E-Mail des Verantwortlichen kommen
aus der .env (DATENSCHUTZ_*), weil das Repo öffentlich ist; der Text der Seite steht im Frontend (pages/Datenschutz.jsx)."""
from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..services import bank_abruf

router = APIRouter(prefix="/api/rechtliches", tags=["rechtliches"])


@router.get("")
def rechtliches():
    return {
        "verantwortlicher": settings.DATENSCHUTZ_VERANTWORTLICHER.replace("\\n", "\n").strip(),
        "email": settings.DATENSCHUTZ_EMAIL.strip(),
        "impressum_url": settings.DATENSCHUTZ_IMPRESSUM_URL,
        "bankabruf": bank_abruf.konfiguriert(),
    }
