"""Fristen: Fälligkeit mit Werktag-Verschiebung (§ 193 BGB).

Fällt das Ende einer Zahlungsfrist auf Samstag, Sonntag oder einen gesetzlichen
Feiertag, gilt der nächste Werktag. Tab kennt kein Bundesland — es zählen nur die
bundesweiten Feiertage (Neujahr, Karfreitag, Ostermontag, 1. Mai, Christi
Himmelfahrt, Pfingstmontag, 3. Oktober, 1. und 2. Weihnachtstag). Landesfeiertage
verschieben die Fälligkeit hier bewusst nicht.

Spiegel in `frontend/src/lib/fristen.js` (Vorschau im Rechnungsformular) —
beide gemeinsam ändern.
"""
from __future__ import annotations

import datetime as dt


def add_days(iso: str, tage: int) -> str:
    return (dt.date.fromisoformat(iso) + dt.timedelta(days=tage)).isoformat()


def tage_zwischen(von: str, bis: str) -> int:
    """Kalendertage von `von` bis `bis` (negativ, wenn `bis` davor liegt)."""
    return (dt.date.fromisoformat(bis) - dt.date.fromisoformat(von)).days


def ostersonntag(jahr: int) -> dt.date:
    """Gaußsche Osterformel (anonymer gregorianischer Algorithmus)."""
    a = jahr % 19
    b, c = divmod(jahr, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    monat = (h + l - 7 * m + 114) // 31
    tag = (h + l - 7 * m + 114) % 31 + 1
    return dt.date(jahr, monat, tag)


def feiertage_bundesweit(jahr: int) -> set[dt.date]:
    ostern = ostersonntag(jahr)
    return {
        dt.date(jahr, 1, 1),
        ostern - dt.timedelta(days=2),   # Karfreitag
        ostern + dt.timedelta(days=1),   # Ostermontag
        dt.date(jahr, 5, 1),
        ostern + dt.timedelta(days=39),  # Christi Himmelfahrt
        ostern + dt.timedelta(days=50),  # Pfingstmontag
        dt.date(jahr, 10, 3),
        dt.date(jahr, 12, 25),
        dt.date(jahr, 12, 26),
    }


def ist_arbeitsfrei(tag: dt.date) -> bool:
    return tag.weekday() >= 5 or tag in feiertage_bundesweit(tag.year)


def naechster_werktag(iso: str) -> str:
    tag = dt.date.fromisoformat(iso)
    while ist_arbeitsfrei(tag):
        tag += dt.timedelta(days=1)
    return tag.isoformat()


def faelligkeit(datum: str, tage: int) -> str:
    """Rechnungsdatum + Zahlungsziel; bei Ziel 0 (sofort) ohne Verschiebung."""
    ende = add_days(datum, tage)
    return ende if tage == 0 else naechster_werktag(ende)
