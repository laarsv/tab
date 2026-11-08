"""Dauerbelege: Ausgaben in festen Abständen mit gleichem Betrag (Miete, Versicherung, Leasing, Abos).

Eine Vorlage hält Bezeichnung, Kategorie, Betrag, Privatanteil und den Rhythmus. `naechste_am` ist der
nächste noch offene Termin. Tab bucht **nie von selbst** — ein Termin ist „fällig“, sobald sein Datum
erreicht ist, und wird dann mit einem Klick (oder über die Bank-Zuordnung) zur Buchung. Die Buchung
trägt `dauerbeleg_id` + `termin`; je Vorlage und Termin gibt es höchstens eine (eindeutiger Index).
Danach rückt der Zeiger auf den nächsten Termin. Einen Termin ohne Ausgabe (mietfreier Monat) überspringt
man, dabei rückt der Zeiger ebenfalls weiter.

Der Tag im Monat bleibt am `anker_tag` hängen: ein Termin am 31. fällt in kürzeren Monaten auf den
Monatsletzten und springt danach zurück.
"""
from __future__ import annotations

import calendar
import datetime as dt
import sqlite3

INTERVALL_MONATE = {"monatlich": 1, "vierteljaehrlich": 3, "halbjaehrlich": 6, "jaehrlich": 12}
MAX_FAELLIG = 60  # so viele nachzuholende Termine zeigt/bucht Tab höchstens auf einmal


class TerminFehler(Exception):
    """Termin passt nicht zum Dauerbeleg (nicht der nächste, pausiert, beendet)."""


def termin_nach(termin: str, intervall: str, anker_tag: int) -> str:
    d = dt.date.fromisoformat(termin)
    m = d.month - 1 + INTERVALL_MONATE[intervall]
    jahr, monat = d.year + m // 12, m % 12 + 1
    tag = min(anker_tag, calendar.monthrange(jahr, monat)[1])
    return dt.date(jahr, monat, tag).isoformat()


def ist_beendet(row: sqlite3.Row | dict) -> bool:
    return bool(row["endet_am"]) and row["naechste_am"] > row["endet_am"]


def faellige_termine(row: sqlite3.Row | dict, heute: str) -> list[str]:
    """Alle noch offenen Termine bis heute (pausierte und beendete Vorlagen haben keine)."""
    if not row["aktiv"] or ist_beendet(row):
        return []
    termine, t = [], row["naechste_am"]
    while t <= heute and (not row["endet_am"] or t <= row["endet_am"]) and len(termine) < MAX_FAELLIG:
        termine.append(t)
        t = termin_nach(t, row["intervall"], row["anker_tag"])
    return termine


def pruefe_termin(row: sqlite3.Row | dict, termin: str) -> None:
    if not row["aktiv"]:
        raise TerminFehler("Der Dauerbeleg ist pausiert.")
    if ist_beendet(row):
        raise TerminFehler("Der Dauerbeleg ist beendet.")
    if termin != row["naechste_am"]:
        raise TerminFehler(
            "Das ist nicht der nächste offene Termin des Dauerbelegs — "
            "frühere Termine zuerst buchen oder überspringen."
        )


def weiterruecken(conn: sqlite3.Connection, row: sqlite3.Row | dict) -> str:
    """Zeiger auf den Termin nach `naechste_am` setzen (ohne Commit); gibt ihn zurück."""
    neu = termin_nach(row["naechste_am"], row["intervall"], row["anker_tag"])
    conn.execute("UPDATE dauerbeleg SET naechste_am = ?, updated_at = datetime('now') WHERE id = ?", (neu, row["id"]))
    return neu


def termin_verbrauchen(conn: sqlite3.Connection, dauerbeleg_id: int, termin: str) -> None:
    """Termin als erledigt festhalten: prüft, dass er der nächste ist, und rückt den Zeiger weiter."""
    row = conn.execute("SELECT * FROM dauerbeleg WHERE id = ?", (dauerbeleg_id,)).fetchone()
    pruefe_termin(row, termin)
    weiterruecken(conn, row)


def faellig_anzahl(conn: sqlite3.Connection, gewerbe_id: int, heute: str) -> int:
    return sum(
        len(faellige_termine(r, heute))
        for r in conn.execute("SELECT * FROM dauerbeleg WHERE gewerbe_id = ? AND aktiv = 1", (gewerbe_id,))
    )
