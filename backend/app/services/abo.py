"""Wiederkehrende Rechnungen (Abos).

Der Scheduler (main.py, alle 6 h + beim Start) erstellt für fällige Abos echte
Rechnungen. Platzhalter {monat} in Positionen/Notiz/Betreff/Mail-Text wird durch
den Abrechnungsmonat (MM/JJJJ des Stichtags) ersetzt; das Leistungsdatum wird
automatisch auf diesen Monat gesetzt.

Auto-Versand nur, wenn aktiviert, Empfänger-Mail vorhanden, der Stichtag höchstens
7 Tage zurückliegt (kein Mail-Schwall nach längerer Server-Pause) und für den
Absender ein App-Passwort hinterlegt ist — sonst bleibt die Rechnung als Entwurf
liegen und wird manuell versendet.
"""
from __future__ import annotations

import calendar
import datetime as dt
import json
import logging
import sqlite3

from .mailer import MailNotConfiguredError, MailSendError, send_mail
from .e_rechnung import rechnungs_pdf
from . import rechnung_summen
from .rechnungen import erstelle_rechnung

log = logging.getLogger("tab.abo")

INTERVALL_MONATE = {"monatlich": 1, "vierteljaehrlich": 3, "jaehrlich": 12}
AUTO_SENDEN_MAX_VERZUG_TAGE = 7


def naechster_termin(datum: dt.date, intervall: str) -> dt.date:
    """Stichtag + Intervall, Monatsende wird geklemmt (31.01. + 1M -> 28./29.02.)."""
    monate = INTERVALL_MONATE[intervall]
    m = datum.month - 1 + monate
    jahr = datum.year + m // 12
    monat = m % 12 + 1
    tag = min(datum.day, calendar.monthrange(jahr, monat)[1])
    return dt.date(jahr, monat, tag)


def ist_beendet(abo: sqlite3.Row | dict, stichtag: dt.date | str | None = None) -> bool:
    """True, wenn der (nächste) Stichtag hinter dem Enddatum liegt — es entsteht keine Rechnung mehr."""
    ende = dict(abo).get("endet_am")
    if not ende:
        return False
    tag = stichtag if stichtag is not None else abo["naechste_am"]
    if isinstance(tag, dt.date):
        tag = tag.isoformat()
    return tag > ende


def beende(conn: sqlite3.Connection, abo_id: int) -> None:
    """Abo ist durch: nicht löschen, nur stilllegen (bleibt in der Liste als „Beendet“)."""
    conn.execute(
        "UPDATE rechnung_abo SET aktiv = 0, updated_at = datetime('now') WHERE id = ?", (abo_id,)
    )


def _ersetze_monat(text: str | None, monat_str: str) -> str | None:
    return text.replace("{monat}", monat_str) if text else text


def erstelle_rechnung_aus_abo(
    conn: sqlite3.Connection, abo: sqlite3.Row | dict, stichtag: dt.date, heute: dt.date
) -> dict:
    """Erstellt die Rechnung für einen Stichtag, versendet ggf. automatisch.

    Gibt {rechnung_id, nummer, versendet: bool, fehler: str|None} zurück. Committet.
    """
    monat_str = f"{stichtag.month:02d}/{stichtag.year}"
    positionen = json.loads(abo["positionen_json"])
    for p in positionen:
        p["beschreibung"] = _ersetze_monat(p["beschreibung"], monat_str)
    # Steuer gegen die Besteuerung im Jahr der neuen Rechnung prüfen. Passt sie nicht (z. B. Wechsel zur
    # Regelbesteuerung, Abo noch ohne Steuersätze), entsteht die Rechnung trotzdem — als Entwurf, ohne Versand.
    steuer_fehler = None
    try:
        hinweis = rechnung_summen.pruefe_steuer(conn, abo["gewerbe_id"], heute.isoformat(), abo["steuerhinweis"], positionen)
    except rechnung_summen.SteuerFehler as e:
        hinweis, steuer_fehler = abo["steuerhinweis"], f"Bitte prüfen: {e}"

    rid = erstelle_rechnung(
        conn,
        gewerbe_id=abo["gewerbe_id"],
        datum=heute.isoformat(),  # Ausstellungsdatum = heute, Leistung = Abrechnungsmonat
        leistungsdatum=monat_str,
        empfaenger_name=abo["empfaenger_name"],
        empfaenger_anschrift=abo["empfaenger_anschrift"],
        empfaenger_email=abo["empfaenger_email"],
        notiz=_ersetze_monat(abo["notiz"], monat_str),
        steuerhinweis=hinweis,
        positionen=positionen,
    )
    conn.commit()
    r = conn.execute("SELECT * FROM rechnung WHERE id = ?", (rid,)).fetchone()

    versendet = False
    fehler = steuer_fehler
    darf_senden = (
        not steuer_fehler
        and abo["auto_senden"]
        and (abo["empfaenger_email"] or "").strip()
        and (heute - stichtag).days <= AUTO_SENDEN_MAX_VERZUG_TAGE
    )
    if darf_senden:
        try:
            gewerbe = conn.execute(
                "SELECT * FROM gewerbe WHERE id = ?", (abo["gewerbe_id"],)
            ).fetchone()
            pos_rows = conn.execute(
                "SELECT * FROM rechnung_position WHERE rechnung_id = ? ORDER BY id", (rid,)
            ).fetchall()
            summe = rechnung_summen.summen(pos_rows)["brutto_cent"]
            pdf = rechnungs_pdf(r, pos_rows, gewerbe)
            betreff = _ersetze_monat(abo["betreff"], monat_str) or f"Rechnung {r['nummer']}"
            text = _ersetze_monat(abo["mail_text"], monat_str) or (
                f"Guten Tag,\n\nanbei erhalten Sie die Rechnung {r['nummer']} "
                f"über {summe // 100},{summe % 100:02d} €.\n\nMit freundlichen Grüßen"
            )
            send_mail(
                conn,
                absender_email=abo["absender_email"],
                absender_name=None,
                an=abo["empfaenger_email"].strip(),
                betreff=betreff,
                text=text,
                anhang=(f"rechnung-{r['nummer']}.pdf", pdf),
            )
            conn.execute(
                "UPDATE rechnung SET status='versendet', versendet_am=?, "
                "updated_at=datetime('now') WHERE id=?",
                (heute.isoformat(), rid),
            )
            conn.commit()
            versendet = True
        except (MailNotConfiguredError, MailSendError) as e:
            fehler = str(e)
            log.warning("Abo %s: Auto-Versand fehlgeschlagen, Rechnung bleibt Entwurf: %s",
                        abo["id"], e)

    return {"rechnung_id": rid, "nummer": r["nummer"], "versendet": versendet, "fehler": fehler}


def run_faellige_abos(conn: sqlite3.Connection, heute: dt.date | None = None) -> list[dict]:
    """Erstellt Rechnungen für alle fälligen Abo-Stichtage (auch verpasste) und
    schiebt naechste_am weiter. Gibt die Ergebnisse zurück.

    Mit Enddatum (endet_am): Stichtage danach erzeugen nichts mehr, das Abo wird stillgelegt."""
    heute = heute or dt.date.today()
    ergebnisse: list[dict] = []
    abos = conn.execute(
        "SELECT * FROM rechnung_abo WHERE aktiv = 1 AND naechste_am <= ?",
        (heute.isoformat(),),
    ).fetchall()
    for abo in abos:
        stichtag = dt.date.fromisoformat(abo["naechste_am"])
        if ist_beendet(abo, stichtag):
            beende(conn, abo["id"])
            conn.commit()
            continue
        while stichtag <= heute:
            try:
                ergebnis = erstelle_rechnung_aus_abo(conn, abo, stichtag, heute)
                ergebnisse.append({"abo_id": abo["id"], **ergebnis})
            except Exception:
                log.exception("Abo %s: Rechnung konnte nicht erstellt werden", abo["id"])
                break  # Abo nicht weiterschieben, nächster Lauf versucht es erneut
            stichtag = naechster_termin(stichtag, abo["intervall"])
            conn.execute(
                "UPDATE rechnung_abo SET naechste_am = ?, updated_at = datetime('now') "
                "WHERE id = ?",
                (stichtag.isoformat(), abo["id"]),
            )
            if ist_beendet(abo, stichtag):
                beende(conn, abo["id"])
                conn.commit()
                break
            conn.commit()
    return ergebnisse
