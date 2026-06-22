"""AfA-Berechnung: linear, monatsgenau pro rata bei Nutzungsdauer > 1;
Vollabzug im Kaufjahr bei Nutzungsdauer = 1 (Hardware/Software-Sofort-Option).

Beträge in Cent (Integer). Rundungsfrei kumulativ, damit die Summe aller
Jahres-AfA exakt den Anschaffungskosten entspricht.
"""
from __future__ import annotations


def _parse_ym(datum: str) -> tuple[int, int]:
    jahr = int(datum[0:4])
    monat = int(datum[5:7])
    return jahr, monat


def jahres_afa_cent(
    anschaffungskosten_cent: int,
    anschaffungsdatum: str,
    nutzungsdauer_jahre: int,
    jahr: int,
) -> int:
    """AfA-Betrag (Cent) eines Wirtschaftsguts für ein bestimmtes Kalenderjahr."""
    acq_year, acq_month = _parse_ym(anschaffungsdatum)
    if jahr < acq_year:
        return 0

    # Sofort-Option: Nutzungsdauer 1 Jahr -> Vollabzug im Anschaffungsjahr.
    if nutzungsdauer_jahre <= 1:
        return anschaffungskosten_cent if jahr == acq_year else 0

    total_months = nutzungsdauer_jahre * 12
    start_index = acq_year * 12 + (acq_month - 1)  # Monat der Anschaffung zählt voll

    def cumulative(through_year: int) -> int:
        end_index = through_year * 12 + 11  # Dezember des Jahres
        elapsed = end_index - start_index + 1
        elapsed = max(0, min(elapsed, total_months))
        return round(anschaffungskosten_cent * elapsed / total_months)

    return cumulative(jahr) - cumulative(jahr - 1)
