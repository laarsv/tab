"""AfA-Berechnung: linear, monatsgenau pro rata bei Nutzungsdauer > 1;
Vollabzug im Kaufjahr bei Nutzungsdauer = 1 (Hardware/Software-Sofort-Option).

Abgang (Verkauf/Entnahme): AfA läuft nur bis einschließlich Abgangsmonat;
der Restbuchwert (AK minus kumulierte AfA) wird berechnet, nicht gespeichert —
er gehört als eigene Buchung in Zeile 38, der Erlös in Zeile 19.

Beträge in Cent (Integer). Rundungsfrei kumulativ, damit die Summe aller
Jahres-AfA exakt den Anschaffungskosten entspricht.
"""
from __future__ import annotations


def _parse_ym(datum: str) -> tuple[int, int]:
    jahr = int(datum[0:4])
    monat = int(datum[5:7])
    return jahr, monat


def _month_cap(
    anschaffungsdatum: str, nutzungsdauer_jahre: int, abgang_datum: str | None
) -> tuple[int, int, int]:
    """(start_index, total_months, cap_index) — cap = letzter AfA-Monat (inkl. Abgang)."""
    acq_year, acq_month = _parse_ym(anschaffungsdatum)
    total_months = nutzungsdauer_jahre * 12
    start_index = acq_year * 12 + (acq_month - 1)  # Monat der Anschaffung zählt voll
    cap = start_index + total_months - 1
    if abgang_datum:
        ab_year, ab_month = _parse_ym(abgang_datum)
        cap = min(cap, ab_year * 12 + (ab_month - 1))
    return start_index, total_months, cap


def jahres_afa_cent(
    anschaffungskosten_cent: int,
    anschaffungsdatum: str,
    nutzungsdauer_jahre: int,
    jahr: int,
    abgang_datum: str | None = None,
) -> int:
    """AfA-Betrag (Cent) eines Wirtschaftsguts für ein bestimmtes Kalenderjahr."""
    acq_year, _ = _parse_ym(anschaffungsdatum)
    if jahr < acq_year:
        return 0

    # Sofort-Option: Nutzungsdauer 1 Jahr -> Vollabzug im Anschaffungsjahr.
    if nutzungsdauer_jahre <= 1:
        return anschaffungskosten_cent if jahr == acq_year else 0

    start_index, total_months, cap = _month_cap(
        anschaffungsdatum, nutzungsdauer_jahre, abgang_datum
    )

    def cumulative(through_year: int) -> int:
        end_index = min(through_year * 12 + 11, cap)  # Dezember bzw. Abgangsmonat
        elapsed = end_index - start_index + 1
        elapsed = max(0, min(elapsed, total_months))
        return round(anschaffungskosten_cent * elapsed / total_months)

    return cumulative(jahr) - cumulative(jahr - 1)


def restbuchwert_cent(
    anschaffungskosten_cent: int,
    anschaffungsdatum: str,
    nutzungsdauer_jahre: int,
    abgang_datum: str | None,
) -> int:
    """Restbuchwert zum Abgang (Cent) = AK minus kumulierte AfA bis Abgangsmonat.

    Ohne Abgang oder bei Sofort-Option (ND 1) ist der Restbuchwert 0.
    """
    if not abgang_datum or nutzungsdauer_jahre <= 1:
        return 0
    start_index, total_months, cap = _month_cap(
        anschaffungsdatum, nutzungsdauer_jahre, abgang_datum
    )
    elapsed = max(0, min(cap - start_index + 1, total_months))
    return anschaffungskosten_cent - round(anschaffungskosten_cent * elapsed / total_months)
