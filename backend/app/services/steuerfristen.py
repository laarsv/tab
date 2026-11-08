"""Steuerfristen für Einzelunternehmer mit EÜR + iCal-Feed für das Kalender-Abo.

Aufbau und Abläufe wie Haben (Seite „Fristen": Überfällig, nächste 30 Tage, später, Kalender-Abo,
Erledigt); Fristen und Code sind eigenständig und auf das beschränkt, was Tab-Nutzer brauchen:

  * **Einkommensteuererklärung mit Anlage EÜR** je Jahr: 31. Juli des Folgejahres ohne
    Steuerberatung (§ 149 Abs. 2 AO), bei Wochenende/Feiertag der nächste Werktag
    (§ 108 Abs. 3 AO). Ab Veranlagungsjahr 2024 (davor galten verlängerte Sonderfristen). Bei
    Gewerbebetrieb gilt dieselbe Frist für die Gewerbesteuererklärung. Mit Steuerberatung gelten
    längere Fristen — die kennt Tab nicht. Erledigt markiert der Nutzer von Hand (Tab überträgt
    nichts ans Finanzamt).
  * **Einkommensteuer-Vorauszahlung** 10.3./10.6./10.9./10.12. — nur Hinweis, nur wenn der Nutzer
    sie einschaltet (ob und wie viel zu zahlen ist, steht im Vorauszahlungsbescheid).
  * Die USt-Voranmeldung fehlt bewusst: Kleinunternehmer geben keine ab, Regelbesteuerung
    unterstützt Tab nicht.
"""
from __future__ import annotations

import datetime as dt
import sqlite3

from .fristen import add_days, naechster_werktag, tage_zwischen

FRUEHESTES_JAHR = 2024  # davor galten verlängerte Sonderfristen, die Tab nicht abbildet
HORIZONT_TAGE = 366
BALD_TAGE = 30
DRINGEND_TAGE = 14  # für den Zähler in der Seitenleiste

ART_LABEL = {"erklaerung": "Erklärung", "vorauszahlung": "Vorauszahlung"}
EST_VORAUSZAHLUNG_TERMINE = ((3, 10), (6, 10), (9, 10), (12, 10))


def _jahre_mit_daten(conn: sqlite3.Connection, gewerbe: list[sqlite3.Row]) -> dict[int, list[str]]:
    """{Jahr: [Gewerbe-Namen mit Buchungen/Rechnungen in dem Jahr]} (ab FRUEHESTES_JAHR)."""
    jahre: dict[int, list[str]] = {}
    for g in gewerbe:
        gesehen: set[int] = set()
        for tabelle in ("buchung", "rechnung"):
            for r in conn.execute(
                f"SELECT DISTINCT CAST(substr(datum, 1, 4) AS INTEGER) AS j FROM {tabelle} "
                "WHERE gewerbe_id = ?",
                (g["id"],),
            ):
                if r["j"] and r["j"] >= FRUEHESTES_JAHR:
                    gesehen.add(r["j"])
        for j in gesehen:
            jahre.setdefault(j, []).append(g["name"])
    return jahre


def erklaerungsfrist(jahr: int) -> str:
    return naechster_werktag(f"{jahr + 1}-07-31")


def steuerfristen(
    conn: sqlite3.Connection,
    *,
    email: str,
    gewerbe: list[sqlite3.Row],
    heute: str,
    est_vorauszahlung: bool,
) -> list[dict]:
    """Alle Fristen, nach Datum sortiert. Offenes aus der Vergangenheit bleibt stehen, bis es
    erledigt ist; kommende Fristen reichen ein Jahr voraus."""
    erledigt = {
        r["schluessel"]: r["erledigt_am"]
        for r in conn.execute("SELECT schluessel, erledigt_am FROM frist_erledigt WHERE email = ?", (email,))
    }
    horizont = add_days(heute, HORIZONT_TAGE)
    jahr_heute = int(heute[:4])
    items: list[dict] = []

    for jahr, namen in _jahre_mit_daten(conn, gewerbe).items():
        if jahr > jahr_heute:
            continue
        faellig = erklaerungsfrist(jahr)
        if faellig > horizont:
            continue
        schluessel = f"steuererklaerung:{jahr}"
        items.append(
            {
                "schluessel": schluessel,
                "art": "erklaerung",
                "titel": f"Einkommensteuererklärung mit Anlage EÜR {jahr}",
                "detail": (
                    f"Abgabe bis {faellig[8:10]}.{faellig[5:7]}.{faellig[:4]} ohne Steuerberatung "
                    f"(31. Juli des Folgejahres, § 149 Abs. 2 AO). Anlage EÜR für: "
                    f"{', '.join(sorted(namen))}. Bei Gewerbebetrieb gilt die Frist auch für die "
                    "Gewerbesteuererklärung. Mit Steuerberatung gelten längere Fristen."
                ),
                "faellig_am": faellig,
                "erledigbar": True,
                "link": "/export",
            }
        )

    if est_vorauszahlung:
        for jahr in (jahr_heute, jahr_heute + 1):
            for monat, tag in EST_VORAUSZAHLUNG_TERMINE:
                faellig = naechster_werktag(f"{jahr}-{monat:02d}-{tag:02d}")
                if not (heute <= faellig <= horizont):
                    continue
                items.append(
                    {
                        "schluessel": f"est-vorauszahlung:{faellig}",
                        "art": "vorauszahlung",
                        "titel": "Einkommensteuer-Vorauszahlung",
                        "detail": (
                            "Nur, wenn das Finanzamt Vorauszahlungen festgesetzt hat — ob und wie "
                            "viel zu zahlen ist, steht im Vorauszahlungsbescheid."
                        ),
                        "faellig_am": faellig,
                        "erledigbar": False,
                        "link": None,
                    }
                )

    for f in items:
        f["erledigt_am"] = erledigt.get(f["schluessel"])
        f["tage_bis"] = tage_zwischen(heute, f["faellig_am"])
        if f["erledigt_am"]:
            f["status"] = "erledigt"
        elif not f["erledigbar"]:
            f["status"] = "hinweis"
        elif f["faellig_am"] < heute:
            f["status"] = "ueberfaellig"
        else:
            f["status"] = "offen"
        f["art_label"] = ART_LABEL[f["art"]]
    items.sort(key=lambda f: (f["faellig_am"], f["schluessel"]))
    return items


def dringend_anzahl(items: list[dict]) -> int:
    """Für den Zähler an „Fristen": offene Erklärungen, überfällig oder in <= 14 Tagen fällig."""
    return sum(
        1
        for f in items
        if f["erledigbar"] and not f["erledigt_am"] and f["tage_bis"] <= DRINGEND_TAGE
    )


# ── iCal ────────────────────────────────────────────────────────────────────

def _ics_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
        .replace("\r\n", "\\n").replace("\n", "\\n")
    )


def _falten(zeile: str) -> list[str]:
    """RFC 5545: Zeilen länger als 75 Oktette umbrechen (Fortsetzung mit führendem Leerzeichen),
    nie mitten in einem UTF-8-Zeichen."""
    roh = zeile.encode("utf-8")
    if len(roh) <= 75:
        return [zeile]
    teile, aktuell, laenge = [], "", 0
    grenze = 75
    for zeichen in zeile:
        b = len(zeichen.encode("utf-8"))
        if laenge + b > grenze:
            teile.append(aktuell)
            aktuell, laenge, grenze = " ", 1, 75  # Fortsetzungszeile: Leerzeichen zählt mit
        aktuell += zeichen
        laenge += b
    teile.append(aktuell)
    return teile


def kalender_ics(items: list[dict], jetzt: dt.datetime | None = None) -> str:
    """Offene Fristen als ganztägige Termine mit Erinnerung 3 Tage vorher (9 Uhr) und am Morgen
    des Tages (9 Uhr). Erledigtes fehlt — es verschwindet beim nächsten Abgleich des Kalenders."""
    jetzt = jetzt or dt.datetime.now(dt.timezone.utc)
    stempel = jetzt.strftime("%Y%m%dT%H%M%SZ")
    zeilen = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//vrwb//Tab Fristen//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Tab Fristen",
        "X-WR-CALDESC:" + _ics_text("Steuerfristen aus Tab"),
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
        "X-PUBLISHED-TTL:PT12H",
    ]
    for f in items:
        if f["erledigt_am"]:
            continue
        start = f["faellig_am"].replace("-", "")
        ende = add_days(f["faellig_am"], 1).replace("-", "")
        titel = f["titel"] + (" (falls festgesetzt)" if f["art"] == "vorauszahlung" else "")
        zeilen += [
            "BEGIN:VEVENT",
            f"UID:{f['schluessel'].replace(':', '-')}@tab.vrwb.de",
            f"DTSTAMP:{stempel}",
            f"DTSTART;VALUE=DATE:{start}",
            f"DTEND;VALUE=DATE:{ende}",
            "SUMMARY:" + _ics_text(titel),
            "DESCRIPTION:" + _ics_text(f["detail"]),
            "TRANSP:TRANSPARENT",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:" + _ics_text(titel + " in 3 Tagen"),
            "TRIGGER:-P2DT15H",  # 3 Tage vorher um 9 Uhr (Ganztagstermine starten um 0 Uhr)
            "END:VALARM",
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            "DESCRIPTION:" + _ics_text(titel + " heute"),
            "TRIGGER:PT9H",  # am Morgen des Tages
            "END:VALARM",
            "END:VEVENT",
        ]
    zeilen.append("END:VCALENDAR")
    gefaltet: list[str] = []
    for z in zeilen:
        gefaltet += _falten(z)
    return "\r\n".join(gefaltet) + "\r\n"
