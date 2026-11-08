"""Zahlungen auf Rechnungen: Teilzahlungen, Skonto, ausgebuchter Rest.

Aufbau nach Haben (Zahlungen mindern den offenen Betrag, Skonto und Forderungsausfall buchen den
Rest aus), eigenständig und auf die EÜR zugeschnitten: **Einnahme ist, was zufließt.** Darum bucht
nur eine echte Zahlung (art 'zahlung') eine Einnahme; Skonto und Ausfall sind Abzüge ohne Buchung.

  offen = Summe − Zahlungen − Ausbuchungen   (nie negativ; bezahlt, sobald 0)

Der Status der Rechnung bleibt 'versendet', bis nichts mehr offen ist, dann 'bezahlt'
(`aktualisiere_status`). Eine Rechnung, die per Status-Knopf als bezahlt markiert wurde, hat eine
Zahlung über die Summe; ältere Rechnungen bekamen sie in Migration v22.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

from .fristen import add_days, naechster_werktag

ARTEN = ("zahlung", "skonto", "ausfall")


def summe_cent(conn: sqlite3.Connection, rechnung_id: int) -> int:
    return sum(
        round(p["menge"] * p["einzelpreis_cent"])
        for p in conn.execute(
            "SELECT menge, einzelpreis_cent FROM rechnung_position WHERE rechnung_id = ?", (rechnung_id,)
        )
    )


def zahlungen_zu(conn: sqlite3.Connection, rechnung_id: int) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM rechnung_zahlung WHERE rechnung_id = ? ORDER BY datum, id", (rechnung_id,)
        )
    ]


def stand(conn: sqlite3.Connection, rechnung: sqlite3.Row | dict) -> dict:
    """Zahlungsstand einer Rechnung (alle Beträge in Cent)."""
    summe = summe_cent(conn, rechnung["id"])
    zahlungen = zahlungen_zu(conn, rechnung["id"])
    bezahlt = sum(z["betrag_cent"] for z in zahlungen if z["art"] == "zahlung")
    ausgebucht = sum(z["betrag_cent"] for z in zahlungen if z["art"] != "zahlung")
    gebucht = sum(z["betrag_cent"] for z in zahlungen if z["art"] == "zahlung" and z["buchung_id"] is not None)
    rest = max(0, summe - bezahlt - ausgebucht)
    status = rechnung["status"]
    if status == "bezahlt" or status == "storniert":
        offen = 0  # der Status gewinnt (z. B. Rundungs-Cent bei Altbestand)
    elif status == "entwurf":
        offen = summe  # noch nicht fällig
    else:
        offen = rest
    return {
        "summe_cent": summe,
        "bezahlt_cent": bezahlt,
        "ausgebucht_cent": ausgebucht,
        "offen_cent": offen,
        "rest_cent": rest,
        "gebucht_cent": gebucht,
        "ungebucht_cent": max(0, bezahlt - gebucht),
        "zahlungen": zahlungen,
    }


def offen_cent(conn: sqlite3.Connection, rechnung: sqlite3.Row | dict) -> int:
    return stand(conn, rechnung)["offen_cent"]


# ── Skonto ──────────────────────────────────────────────────────────────────

def skonto_cent(summe: int, skonto_bp: int | None) -> int:
    """Skonto-Betrag, kaufmännisch gerundet."""
    return 0 if not skonto_bp else (summe * skonto_bp + 5_000) // 10_000


def skonto_bis(datum: str, skonto_tage: int | None) -> str | None:
    return add_days(datum, skonto_tage) if skonto_tage else None


def skonto_gilt(rechnung: sqlite3.Row | dict, zahlungsdatum: str) -> bool:
    """Skonto gilt bis zum Fristende; endet es auf Wochenende/Feiertag, zählt auch der nächste
    Werktag (§ 193 BGB)."""
    bis = skonto_bis(rechnung["datum"], rechnung["skonto_tage"])
    return bool(rechnung["skonto_bp"] and bis and zahlungsdatum <= naechster_werktag(bis))


# ── Schreiben ───────────────────────────────────────────────────────────────

def zahlung_anlegen(
    conn: sqlite3.Connection,
    *,
    rechnung: sqlite3.Row | dict,
    datum: str,
    betrag_cent: int,
    art: str = "zahlung",
    buchung_id: int | None = None,
    umsatz_id: int | None = None,
    notiz: str | None = None,
) -> int:
    assert art in ARTEN
    cur = conn.execute(
        "INSERT INTO rechnung_zahlung (rechnung_id, gewerbe_id, datum, betrag_cent, art, buchung_id, bank_umsatz_id, notiz) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (rechnung["id"], rechnung["gewerbe_id"], datum, betrag_cent, art, buchung_id, umsatz_id, (notiz or "").strip() or None),
    )
    return cur.lastrowid


def aktualisiere_status(conn: sqlite3.Connection, rechnung_id: int) -> None:
    """versendet ⇄ bezahlt je nachdem, ob noch etwas offen ist; `bezahlt_am` = Tag der letzten Zahlung."""
    r = conn.execute("SELECT * FROM rechnung WHERE id = ?", (rechnung_id,)).fetchone()
    if r is None or r["status"] not in ("versendet", "bezahlt"):
        return
    summe = summe_cent(conn, rechnung_id)
    zahlungen = zahlungen_zu(conn, rechnung_id)
    erledigt = sum(z["betrag_cent"] for z in zahlungen)
    if zahlungen and erledigt >= summe:
        letzte = max(z["datum"] for z in zahlungen)
        conn.execute(
            "UPDATE rechnung SET status = 'bezahlt', bezahlt_am = ?, updated_at = datetime('now') WHERE id = ?",
            (letzte, rechnung_id),
        )
    elif r["status"] == "bezahlt":
        conn.execute(
            "UPDATE rechnung SET status = 'versendet', bezahlt_am = NULL, updated_at = datetime('now') WHERE id = ?",
            (rechnung_id,),
        )


def einnahme_buchen(
    conn: sqlite3.Connection, rechnung: sqlite3.Row | dict, datum: str, betrag_cent: int, teilzahlung: bool
) -> int:
    """Einnahme-Buchung zu einer Zahlung (Kategorie nach Steuerhinweis, wie „Als Einnahme buchen“)."""
    key = "einnahme_steuerfrei" if rechnung["steuerhinweis"] == "vers4nr11" else "einnahme_ku"
    kat = conn.execute("SELECT id FROM kategorie WHERE key = ?", (key,)).fetchone()
    beschreibung = f"Rechnung {rechnung['nummer']} – {rechnung['empfaenger_name']}" + (" (Teilzahlung)" if teilzahlung else "")
    cur = conn.execute(
        "INSERT INTO buchung (gewerbe_id, datum, beschreibung) VALUES (?, ?, ?)",
        (rechnung["gewerbe_id"], datum, beschreibung),
    )
    conn.execute(
        "INSERT INTO buchung_position (buchung_id, kategorie_id, betrag_cent) VALUES (?, ?, ?)",
        (cur.lastrowid, kat["id"], betrag_cent),
    )
    conn.execute("UPDATE rechnung SET buchung_id = ? WHERE id = ?", (cur.lastrowid, rechnung["id"]))
    return cur.lastrowid


def heute() -> str:
    return dt.date.today().isoformat()
