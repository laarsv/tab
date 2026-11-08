"""Rechte der Steuerberatung: nur lesen, nur eine feste Liste von Abfragen.

Eine Allowlist statt Sperrliste: Was hier nicht steht, ist für die Steuerberatung zu — auch jede neue Route, die
später dazukommt, bis sie jemand bewusst freigibt. Greift als Middleware (main.py) vor jeder Route, unabhängig davon,
ob die einzelne Route an die Rolle denkt. Zusätzlich liefert get_current_user für diese Sitzungen den Inhaber nur mit
rolle = "steuerberatung", und ist_admin() ist für sie immer False.
"""
from __future__ import annotations

import re

# Nur GET. Journal, Auswertung, Belege, festgeschriebene Rechnungen, Anlagen/Fahrten, Abschluss-Stand und Protokoll.
LESEN = [
    r"/api/auth/(me|methoden)",
    r"/api/gewerbe",
    r"/api/kategorien",
    r"/api/meta/jahre",
    r"/api/kennzahlen",
    r"/api/buchungen",
    r"/api/buchungen/\d+/belege",
    r"/api/belege",
    r"/api/belege/\d+/download",
    r"/api/afa",
    r"/api/fahrten",
    r"/api/rechnungen",
    r"/api/rechnungen/\d+/pdf",
    r"/api/export/(summenblatt|summenblatt\.csv|journal\.csv|belege\.zip)",
    r"/api/abschluss",
    r"/api/abschluss/status",
    r"/api/abschluss/protokoll",
    r"/api/abschluss/protokoll\.csv",
]
# Schreibend erlaubt, weil sie nichts am Bestand ändern: abmelden, selbst (neu) anmelden.
SCHREIBEN = [
    r"/api/auth/logout",
    r"/api/berater/login",
    r"/api/berater/einladung/[^/]+/annehmen",
]

_LESEN = [re.compile(p) for p in LESEN]
_SCHREIBEN = [re.compile(p) for p in SCHREIBEN]


def berater_erlaubt(method: str, path: str) -> bool:
    muster = _LESEN if method == "GET" else _SCHREIBEN if method == "POST" else []
    return any(m.fullmatch(path.rstrip("/") or "/") for m in muster)
