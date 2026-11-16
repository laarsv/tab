"""Umsatzsteuer-Voranmeldung (UStVA) für Gewerbe mit Regelbesteuerung, Ist-Versteuerung (EUER_KATEGORIEN.md §9).

Tab rechnet die Werte für das ELSTER-Formular aus, übermittelt aber nichts. Grundlage sind dieselben
Buchungspositionen wie im EÜR-Summenblatt (Datum = Zahlungstag), deshalb passen Voranmeldungen und Anlage EÜR
(Z15/Z17/Vorsteuer-Zeile) zusammen:

  * Kz 81 / 86: Netto der Einnahmen zu 19 % / 7 % (Bemessungsgrundlage in vollen Euro, abgerundet); die Steuer
    rechnet ELSTER aus der Bemessungsgrundlage — Tab zeigt denselben Wert und daneben die gebuchte Steuer.
  * Kz 35 / 36: Einnahmen zu anderen Steuersätzen (Bemessungsgrundlage / gebuchte Steuer).
  * Kz 48: steuerfreie Umsätze ohne Vorsteuerabzug (Kategorie `einnahme_steuerfrei`, § 4 Nr. 11 Courtage).
  * Kz 66: Vorsteuer — betrieblicher Teil der Steuer auf Ausgaben (Privatanteil gilt auch für die Steuer,
    Bewirtung voll) plus `afa_buchung.vorsteuer_cent` im Anschaffungsmonat.
  * Kz 83: verbleibende Vorauszahlung (negativ = Überschuss/Erstattung).

Bewusst vereinfacht: Vorsteuer zählt am Zahlungstag (Buchungsdatum), nicht am Rechnungseingang; keine
Vorsteueraufteilung bei steuerfreien Umsätzen (nur Hinweis), kein § 13b, kein innergemeinschaftlicher Erwerb,
keine Sondervorauszahlung (Kz 39), keine Berichtigung nach § 15a.
"""
from __future__ import annotations

import calendar
import sqlite3

from . import besteuerung as best
from .fristen import add_days, naechster_werktag
from .privatanteil import betrieblich_ust_cent

ZEITRAEUME = ("monat", "quartal", "jahr")
ZEITRAUM_LABEL = {"monat": "monatlich", "quartal": "vierteljährlich", "jahr": "keine Voranmeldung (nur Jahreserklärung)"}
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober",
          "November", "Dezember")

KZ_LABEL = {
    "81": "Steuerpflichtige Umsätze zu 19 %",
    "86": "Steuerpflichtige Umsätze zu 7 %",
    "35": "Umsätze zu anderen Steuersätzen",
    "48": "Steuerfreie Umsätze ohne Vorsteuerabzug (§ 4 Nr. 8–29 UStG)",
    "66": "Vorsteuerbeträge aus Rechnungen von anderen Unternehmern",
    "83": "Verbleibende Umsatzsteuer-Vorauszahlung bzw. Überschuss",
}


def zeitraeume(jahr: int, art: str) -> list[dict]:
    """Voranmeldungszeiträume eines Jahres: [{key, label, von, bis}]. `art` = monat | quartal."""
    out = []
    if art == "monat":
        for m in range(1, 13):
            out.append({"key": f"{jahr}-{m:02d}", "label": f"{MONATE[m - 1]} {jahr}",
                        "von": f"{jahr}-{m:02d}-01", "bis": f"{jahr}-{m:02d}-{calendar.monthrange(jahr, m)[1]:02d}"})
    elif art == "quartal":
        for q in range(1, 5):
            m_bis = q * 3
            out.append({"key": f"{jahr}-Q{q}", "label": f"{q}. Quartal {jahr}",
                        "von": f"{jahr}-{m_bis - 2:02d}-01",
                        "bis": f"{jahr}-{m_bis:02d}-{calendar.monthrange(jahr, m_bis)[1]:02d}"})
    return out


def abgabefrist(bis: str, dauerfrist: bool) -> str:
    """10. Tag nach Ablauf des Zeitraums (§ 18 Abs. 1 UStG), mit Dauerfristverlängerung einen Monat später
    (§ 46 UStDV); Wochenende/Feiertag → nächster Werktag (§ 108 Abs. 3 AO)."""
    j, m = int(bis[:4]), int(bis[5:7]) + (2 if dauerfrist else 1)
    if m > 12:
        j, m = j + 1, m - 12
    return naechster_werktag(f"{j}-{m:02d}-10")


def jahreserklaerung_frist(jahr: int) -> str:
    """Umsatzsteuererklärung: 31. Juli des Folgejahres ohne Steuerberatung (§ 149 Abs. 2 AO)."""
    return naechster_werktag(f"{jahr + 1}-07-31")


def _euro_ab(cent: int) -> int:
    """Bemessungsgrundlage in vollen Euro, zugunsten des Unternehmers abgerundet (bei negativ: Richtung 0)."""
    return int(cent / 100)


def _eur(cent: int) -> str:
    return f"{cent / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def berechne(conn: sqlite3.Connection, gewerbe_id: int, von: str, bis: str, mit_positionen: bool = False) -> dict:
    """Kennzahlen für den Zeitraum von..bis (beide einschließlich, innerhalb eines Jahres)."""
    netto: dict[int, int] = {}  # Einnahmen netto je Satz (bp)
    steuer: dict[int, int] = {}  # gebuchte Steuer je Satz
    steuerfrei = vorsteuer = nicht_erfasst = gezahlt = erstattet = 0
    positionen: list[dict] = []

    rows = conn.execute(
        "SELECT b.id AS buchung_id, b.datum, b.beschreibung, p.betrag_cent, p.ust_bp, p.ust_cent, p.privat_bp, "
        "k.key, k.name, k.typ FROM buchung_position p JOIN buchung b ON b.id = p.buchung_id "
        "JOIN kategorie k ON k.id = p.kategorie_id "
        "WHERE b.gewerbe_id = ? AND b.datum BETWEEN ? AND ? ORDER BY b.datum, b.id, p.id",
        (gewerbe_id, von, bis),
    ).fetchall()
    for r in rows:
        kz, bmg, st = None, 0, 0
        if r["key"] == "ust_zahlung":
            gezahlt += r["betrag_cent"]
        elif r["key"] == "ust_erstattung":
            erstattet += r["betrag_cent"]
        elif r["typ"] == "einnahme":
            if r["ust_bp"]:
                bmg, st = r["betrag_cent"] - r["ust_cent"], r["ust_cent"]
                netto[r["ust_bp"]] = netto.get(r["ust_bp"], 0) + bmg
                steuer[r["ust_bp"]] = steuer.get(r["ust_bp"], 0) + st
                kz = {1900: "81", 700: "86"}.get(r["ust_bp"], "35")
            elif r["key"] == "einnahme_steuerfrei":
                bmg, kz = r["betrag_cent"], "48"
                steuerfrei += bmg
            else:
                bmg = r["betrag_cent"]
                nicht_erfasst += bmg
        else:
            st = betrieblich_ust_cent(r["ust_cent"], r["privat_bp"])
            if st:
                vorsteuer += st
                kz = "66"
        if mit_positionen and (kz or r["key"] in ("ust_zahlung", "ust_erstattung") or r["typ"] == "einnahme"):
            positionen.append({
                "buchung_id": r["buchung_id"], "datum": r["datum"], "beschreibung": r["beschreibung"],
                "kategorie": r["name"], "typ": r["typ"], "betrag_cent": r["betrag_cent"], "ust_bp": r["ust_bp"],
                "steuer_cent": st, "kz": kz,
            })

    for r in conn.execute(
        "SELECT id, bezeichnung, anschaffungsdatum, vorsteuer_cent FROM afa_buchung "
        "WHERE gewerbe_id = ? AND vorsteuer_cent > 0 AND anschaffungsdatum BETWEEN ? AND ?",
        (gewerbe_id, von, bis),
    ):
        vorsteuer += r["vorsteuer_cent"]
        if mit_positionen:
            positionen.append({
                "buchung_id": None, "afa_id": r["id"], "datum": r["anschaffungsdatum"],
                "beschreibung": f"Anschaffung: {r['bezeichnung']}", "kategorie": "Abschreibung", "typ": "ausgabe",
                "betrag_cent": None, "ust_bp": None, "steuer_cent": r["vorsteuer_cent"], "kz": "66",
            })

    kz81_eur = _euro_ab(netto.get(1900, 0))
    kz86_eur = _euro_ab(netto.get(700, 0))
    andere_netto = sum(v for bp, v in netto.items() if bp not in (1900, 700))
    andere_steuer = sum(v for bp, v in steuer.items() if bp not in (1900, 700))
    st81 = kz81_eur * 19  # Cent: ELSTER rechnet 19 % der Bemessungsgrundlage in vollen Euro
    st86 = kz86_eur * 7
    kz83 = st81 + st86 + andere_steuer - vorsteuer

    kennzahlen = []
    if kz81_eur or netto.get(1900):
        kennzahlen.append({"kz": "81", "label": KZ_LABEL["81"], "bemessung_eur": kz81_eur, "steuer_cent": st81,
                           "gebucht_cent": steuer.get(1900, 0)})
    if kz86_eur or netto.get(700):
        kennzahlen.append({"kz": "86", "label": KZ_LABEL["86"], "bemessung_eur": kz86_eur, "steuer_cent": st86,
                           "gebucht_cent": steuer.get(700, 0)})
    if andere_netto:
        kennzahlen.append({"kz": "35", "label": KZ_LABEL["35"], "bemessung_eur": _euro_ab(andere_netto),
                           "steuer_cent": andere_steuer, "steuer_kz": "36", "gebucht_cent": andere_steuer})
    if steuerfrei:
        kennzahlen.append({"kz": "48", "label": KZ_LABEL["48"], "bemessung_eur": _euro_ab(steuerfrei)})
    if vorsteuer:
        kennzahlen.append({"kz": "66", "label": KZ_LABEL["66"], "steuer_cent": vorsteuer})
    kennzahlen.append({"kz": "83", "label": KZ_LABEL["83"], "steuer_cent": kz83})

    hinweise = []
    if steuerfrei and vorsteuer:
        hinweise.append(
            "Neben steuerpflichtigen gibt es steuerfreie Umsätze (§ 4 Nr. 11). Vorsteuer, die zu den steuerfreien "
            "Umsätzen gehört, ist nicht abziehbar (§ 15 Abs. 2 UStG) — Tab teilt sie nicht auf. Bitte mit der "
            "Steuerberatung klären, welcher Teil der Vorsteuer abziehbar ist."
        )
    if nicht_erfasst:
        hinweise.append(
            f"Einnahmen ohne Steuersatz über {_eur(nicht_erfasst)} (z. B. Zinsen, Erstattungen) stehen nicht in "
            "der Voranmeldung. Wenn das Umsätze sind, die Buchung mit Steuersatz erfassen."
        )
    out = {
        "von": von, "bis": bis,
        "kennzahlen": kennzahlen,
        "kz83_cent": kz83,
        "umsatzsteuer_cent": st81 + st86 + andere_steuer,
        "vorsteuer_cent": vorsteuer,
        "gebuchte_ust_cent": sum(steuer.values()),
        "nicht_erfasst_cent": nicht_erfasst,
        "gezahlt_cent": gezahlt,
        "erstattet_cent": erstattet,
        "hinweise": hinweise,
        "leer": not rows and not vorsteuer,
    }
    if mit_positionen:
        out["positionen"] = positionen
    return out


def frist_schluessel(gewerbe_id: int, key: str) -> str:
    return f"ustva:{gewerbe_id}:{key}"


def jahreserklaerung_schluessel(gewerbe_id: int, jahr: int) -> str:
    return f"ust-erklaerung:{gewerbe_id}:{jahr}"


def regel_jahre(conn: sqlite3.Connection, gewerbe_id: int, bis_jahr: int, ab_jahr: int = 2024) -> list[int]:
    """Jahre mit Regelbesteuerung von ab_jahr bis bis_jahr (für Fristen)."""
    if not conn.execute("SELECT 1 FROM gewerbe_besteuerung WHERE gewerbe_id = ? AND art = ?",
                        (gewerbe_id, best.REGEL)).fetchone():
        return []
    return [j for j in range(ab_jahr, bis_jahr + 1) if best.ist_regel(conn, gewerbe_id, j)]
