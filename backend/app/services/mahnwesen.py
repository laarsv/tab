"""Mahnwesen: Überfälligkeit, Mahnbeträge (Gebühr, Verzugspauschale, Verzugszinsen) und
Abfragen. Aufbau und Abläufe orientieren sich an Haben (Mahnwesen-Reiter, Stufen,
Forderungsaufstellung); Texte und Code sind eigenständig.

Stufen: 1 Zahlungserinnerung, 2 1. Mahnung, 3 Letzte Mahnung. Mahnungen sind
unveränderliche Schnappschüsse (Tabelle `mahnung`).

Rechenregeln:
  * Verzugszinsen = offener Betrag x (Basiszinssatz + Aufschlag) x Tage / 365, kaufmännisch
    gerundet, ab dem Tag NACH der Fälligkeit bis zum Mahndatum. Aufschlag § 288 BGB:
    Unternehmer 9 Prozentpunkte, Verbraucher 5. Vereinfacht mit 365 Tagen je Jahr.
  * Verzugspauschale 40 EUR (§ 288 Abs. 5 BGB, nur gegenüber Unternehmern). Sie wird auf eine
    Mahngebühr angerechnet (Satz 3): gefordert wird die Pauschale plus nur der Teil der
    Gebühr, der sie übersteigt.
  * Hat eine Rechnung keine Fälligkeit (Bestand vor v17), gilt Rechnungsdatum + 30 Tage
    (Verzug spätestens 30 Tage nach Zugang, § 286 Abs. 3 BGB).
  * Gemahnt wird der offene Rest nach Teilzahlungen, Skonto und Ausbuchungen (services/zahlungen.py).
"""
from __future__ import annotations

import sqlite3

from .fristen import add_days, tage_zwischen
from .zahlungen import offen_cent, summe_cent  # noqa: F401 (summe_cent: von anderen Modulen hier importiert)

STUFEN = {
    1: {"label": "Zahlungserinnerung", "titel": "Zahlungserinnerung"},
    2: {"label": "1. Mahnung", "titel": "Mahnung"},
    3: {"label": "Letzte Mahnung", "titel": "Letzte Mahnung"},
}

# Vorschläge für Einleitung und Schluss je Stufe — im Formular frei änderbar.
TEXTE = {
    1: {
        "einleitung": (
            "bei der Durchsicht unserer Buchhaltung ist uns aufgefallen, dass für die unten "
            "genannte Rechnung noch kein Zahlungseingang vorliegt. Bitte überweisen Sie den "
            "offenen Betrag bis zum genannten Datum."
        ),
        "schluss": (
            "Sollte sich Ihre Zahlung mit diesem Schreiben überschnitten haben, betrachten "
            "Sie es bitte als gegenstandslos."
        ),
    },
    2: {
        "einleitung": (
            "auf unsere Zahlungserinnerung haben wir bisher keinen Zahlungseingang festgestellt. "
            "Bitte begleichen Sie den offenen Betrag samt der unten aufgeführten Kosten bis "
            "zum genannten Datum."
        ),
        "schluss": (
            "Sollte sich Ihre Zahlung mit diesem Schreiben überschnitten haben, betrachten "
            "Sie es bitte als gegenstandslos."
        ),
    },
    3: {
        "einleitung": (
            "trotz Zahlungserinnerung und Mahnung ist die unten genannte Rechnung weiterhin "
            "offen. Wir fordern Sie letztmalig auf, den Gesamtbetrag bis zum genannten Datum "
            "zu überweisen."
        ),
        "schluss": (
            "Geht die Zahlung nicht fristgerecht ein, behalten wir uns vor, ohne weitere "
            "Ankündigung gerichtliche Schritte einzuleiten. Die dadurch entstehenden Kosten "
            "gehen zu Ihren Lasten."
        ),
    },
}

# Aufschlag auf den Basiszinssatz in Basispunkten (§ 288 BGB).
AUFSCHLAG_BP = {"geschaeftskunde": 900, "verbraucher": 500}
PAUSCHALE_CENT = 40_00
VERZUG_OHNE_ZIEL_TAGE = 30


def effektive_faelligkeit(datum: str, faellig_am: str | None) -> str:
    return faellig_am or add_days(datum, VERZUG_OHNE_ZIEL_TAGE)


def tage_ueberfaellig(faellig: str, heute: str) -> int:
    """Verzugstage: ab dem Tag nach der Fälligkeit bis einschließlich `heute`."""
    return max(0, tage_zwischen(faellig, heute))


def verzugszinsen_cent(offen_cent: int, satz_bp: int, tage: int) -> int:
    if offen_cent <= 0 or satz_bp <= 0 or tage <= 0:
        return 0
    nenner = 10_000 * 365
    return (2 * offen_cent * satz_bp * tage + nenner) // (2 * nenner)  # kaufmännisch gerundet


def mahnbetraege(
    *,
    offen_cent: int,
    faellig: str,
    datum: str,
    gebuehr_cent: int,
    pauschale: bool,
    zinssatz_bp: int | None,
) -> dict:
    """Beträge der Forderungsaufstellung. `zinssatz_bp` = Basiszins + Aufschlag, None = keine Zinsen."""
    zinstage = 0 if zinssatz_bp is None else tage_ueberfaellig(faellig, datum)
    zinsen = 0 if zinssatz_bp is None else verzugszinsen_cent(offen_cent, zinssatz_bp, zinstage)
    pauschale_cent = PAUSCHALE_CENT if pauschale else 0
    gebuehr = max(0, gebuehr_cent - pauschale_cent)
    return {
        "offen_cent": offen_cent,
        "gebuehr_cent": gebuehr,
        "pauschale_cent": pauschale_cent,
        "zinsen_cent": zinsen,
        "zinssatz_bp": zinssatz_bp or 0,
        "zinstage": zinstage,
        "gesamt_cent": offen_cent + gebuehr + pauschale_cent + zinsen,
    }


# ── Abfragen ────────────────────────────────────────────────────────────────

def mahnungen_zu(conn: sqlite3.Connection, rechnung_id: int) -> list[dict]:
    """Alle Mahnungen einer Rechnung, neueste zuerst."""
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM mahnung WHERE rechnung_id = ? ORDER BY datum DESC, id DESC",
            (rechnung_id,),
        )
    ]


def naechste_stufe(letzte: dict | None) -> int:
    return min((letzte["stufe"] if letzte else 0) + 1, 3)


def ueberfaellige(conn: sqlite3.Connection, gewerbe_id: int, heute: str) -> list[dict]:
    """Versendete, noch nicht bezahlte Rechnungen mit abgelaufener Fälligkeit,
    am längsten überfällige zuerst — je mit letzter Mahnung und nächster Stufe."""
    items = []
    for r in conn.execute(
        "SELECT * FROM rechnung WHERE gewerbe_id = ? AND status = 'versendet'", (gewerbe_id,)
    ):
        faellig = effektive_faelligkeit(r["datum"], r["faellig_am"])
        if faellig >= heute:
            continue
        offen = offen_cent(conn, r)  # nach Teilzahlungen/Skonto
        if offen <= 0:
            continue
        mahnungen = mahnungen_zu(conn, r["id"])
        letzte = mahnungen[0] if mahnungen else None
        items.append(
            {
                "id": r["id"],
                "nummer": r["nummer"],
                "datum": r["datum"],
                "empfaenger_name": r["empfaenger_name"],
                "faellig_am": faellig,
                "ohne_ziel": r["faellig_am"] is None,
                "tage_ueberfaellig": tage_ueberfaellig(faellig, heute),
                "offen_cent": offen,
                "letzte_mahnung": letzte,
                "anzahl_mahnungen": len(mahnungen),
                "naechste_stufe": naechste_stufe(letzte),
                # Frist der letzten Mahnung läuft noch -> nächste Stufe ist noch nicht dran
                "wartet": bool(letzte and letzte["frist_am"] >= heute),
            }
        )
    items.sort(key=lambda i: -i["tage_ueberfaellig"])
    return items
