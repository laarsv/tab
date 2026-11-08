"""AfA-Berechnung. Methoden (Spalte `afa_methode`):

  * linear        monatsgenau pro rata bei Nutzungsdauer > 1; Vollabzug im Kaufjahr bei Nutzungsdauer = 1
                  (Hardware/Software-Sofort-Option). Die Rechnung ist seit jeher unverändert.
  * degressiv     fester Satz vom Buchwert am Jahresanfang (§ 7 Abs. 2 EStG), im Anschaffungsjahr ab dem
                  Anschaffungsmonat; Wechsel zur linearen AfA, sobald diese höher ist (§ 7 Abs. 3 EStG) oder
                  ab einem gewählten Jahr. Nur für Anschaffungen in den Zeitfenstern von `degressiv_grenze`.
  * elektro       Staffel 75/10/5/5/3/2 % (§ 7 Abs. 2a EStG), Anschaffung 01.07.2025–31.12.2027.
  * sammelposten  je ein Fünftel im Anschaffungsjahr und den vier Folgejahren (§ 6 Abs. 2a EStG),
                  unabhängig vom Monat; ein Abgang ändert daran nichts.

Abgang (Verkauf/Entnahme): AfA läuft nur bis einschließlich Abgangsmonat;
der Restbuchwert (AK minus kumulierte AfA) wird berechnet, nicht gespeichert —
er gehört als eigene Buchung in die Restbuchwert-Zeile (2025: 38, 2026: 39), der Erlös
in Zeile 19.

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


def _linear_jahr_cent(
    anschaffungskosten_cent: int,
    anschaffungsdatum: str,
    nutzungsdauer_jahre: int,
    jahr: int,
    abgang_datum: str | None = None,
) -> int:
    """Lineare AfA (Cent) für ein Kalenderjahr."""
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


def _linear_restbuchwert_cent(
    anschaffungskosten_cent: int,
    anschaffungsdatum: str,
    nutzungsdauer_jahre: int,
    abgang_datum: str | None,
) -> int:
    """Restbuchwert zum Abgang (Cent) = AK minus kumulierte lineare AfA bis Abgangsmonat.

    Ohne Abgang oder bei Sofort-Option (ND 1) ist der Restbuchwert 0.
    """
    if not abgang_datum or nutzungsdauer_jahre <= 1:
        return 0
    start_index, total_months, cap = _month_cap(
        anschaffungsdatum, nutzungsdauer_jahre, abgang_datum
    )
    elapsed = max(0, min(cap - start_index + 1, total_months))
    return anschaffungskosten_cent - round(anschaffungskosten_cent * elapsed / total_months)


# ── Methoden ────────────────────────────────────────────────────────────────

METHODEN = ("linear", "degressiv", "elektro", "sammelposten")
METHODEN_NAME = {
    "linear": "Linear",
    "degressiv": "Degressiv",
    "elektro": "Elektrofahrzeug (§ 7 Abs. 2a EStG)",
    "sammelposten": "Sammelposten (§ 6 Abs. 2a EStG)",
}

ELEKTRO_STAFFEL_BP = (7500, 1000, 500, 500, 300, 200)  # Jahr 1 … 6, Summe 100 %
ELEKTRO_JAHRE = len(ELEKTRO_STAFFEL_BP)
ELEKTRO_FENSTER = ("2025-07-01", "2027-12-31")
SAMMELPOSTEN_JAHRE = 5
SAMMELPOSTEN_VON_CENT = 25_001  # 250,01 €
SAMMELPOSTEN_BIS_CENT = 100_000  # 1.000 €

# (von, bis, Vielfaches des linearen Satzes in Zehnteln, Höchstsatz in Basispunkten)
DEGRESSIV_FENSTER = (
    ("2025-07-01", "2027-12-31", 30, 3000),  # Dreifaches, höchstens 30 %
    ("2024-04-01", "2024-12-31", 20, 2000),  # Doppeltes, höchstens 20 %
    ("2020-01-01", "2022-12-31", 25, 2500),  # Zweieinhalbfaches, höchstens 25 %
)


def _prozent(bp: int) -> str:
    """Basispunkte als deutsche Prozentzahl: 3000 -> '30', 2307 -> '23,07'."""
    return f"{bp / 100:g}".replace(".", ",")


def _div_round(a: int, b: int) -> int:
    """a / b kaufmännisch gerundet (positive Ganzzahlen)."""
    return (2 * a + b) // (2 * b)


def degressiv_grenze(anschaffungsdatum: str, nutzungsdauer_jahre: int) -> tuple[int | None, str | None]:
    """(Höchstsatz in Basispunkten, Grund) — Höchstsatz None, wenn degressiv nicht möglich ist."""
    if nutzungsdauer_jahre < 2:
        return None, "Degressiv braucht eine Nutzungsdauer von mindestens 2 Jahren."
    for von, bis, zehntel, kappe in DEGRESSIV_FENSTER:
        if von <= anschaffungsdatum <= bis:
            # Vielfaches des linearen Satzes (10000 / ND Basispunkte), abgerundet, höchstens die Kappe
            return min(kappe, zehntel * 1000 // nutzungsdauer_jahre), None
    return None, (
        "Degressive AfA gibt es nur für Anschaffungen vom 01.07.2025 bis 31.12.2027 "
        "(außerdem 01.04.–31.12.2024 und 2020–2022)."
    )


def elektro_moeglich(anschaffungsdatum: str) -> bool:
    return ELEKTRO_FENSTER[0] <= anschaffungsdatum <= ELEKTRO_FENSTER[1]


def optionen(anschaffungsdatum: str, nutzungsdauer_jahre: int) -> dict:
    """Welche Methoden für diese Anschaffung zulässig sind (das Formular zeigt nur diese)."""
    max_bp, grund = degressiv_grenze(anschaffungsdatum, nutzungsdauer_jahre)
    return {
        "degressiv": {"moeglich": max_bp is not None, "max_bp": max_bp, "grund": grund},
        "elektro": {
            "moeglich": elektro_moeglich(anschaffungsdatum),
            "grund": None if elektro_moeglich(anschaffungsdatum)
            else "Die Staffel gilt für Elektrofahrzeuge, die vom 01.07.2025 bis 31.12.2027 angeschafft wurden.",
        },
        "sammelposten": {"moeglich": True, "grund": None},
    }


def _schedule_degressiv(
    ak: int, datum: str, nd: int, bp: int, linear_ab_jahr: int | None, abgang_datum: str | None
) -> list[dict]:
    """[{jahr, afa_cent, linear}] — degressiv vom Buchwert, Wechsel zur linearen AfA über die Restmonate."""
    y0, m0 = _parse_ym(datum)
    abgang = _parse_ym(abgang_datum) if abgang_datum else None
    total = nd * 12
    zeilen: list[dict] = []
    buchwert, verbraucht, jahr, linear = ak, 0, y0, False
    while buchwert > 0 and verbraucht < total:
        erster = m0 if jahr == y0 else 1
        letzter = abgang[1] if abgang and abgang[0] == jahr else 12
        monate = min(letzter - erster + 1, total - verbraucht)
        if monate <= 0:
            break
        rest = total - verbraucht
        if not linear:
            deg = _div_round(buchwert * bp * monate, 10000 * 12)
            lin = _div_round(buchwert * monate, rest)
            linear = lin >= deg or (linear_ab_jahr is not None and jahr >= linear_ab_jahr)
        afa = buchwert if monate == rest else _div_round(buchwert * monate, rest) if linear else _div_round(buchwert * bp * monate, 10000 * 12)
        afa = min(afa, buchwert)
        zeilen.append({"jahr": jahr, "afa_cent": afa, "linear": linear})
        buchwert -= afa
        verbraucht += monate
        if abgang and abgang[0] == jahr:
            break
        jahr += 1
    return zeilen


def _schedule_elektro(ak: int, datum: str, abgang_datum: str | None) -> list[dict]:
    y0, _ = _parse_ym(datum)
    abgang = _parse_ym(abgang_datum) if abgang_datum else None
    zeilen, summe = [], 0
    for i, anteil in enumerate(ELEKTRO_STAFFEL_BP):
        jahr = y0 + i
        if abgang and jahr > abgang[0]:
            break
        # letztes Staffeljahr nimmt den Rundungsrest mit, damit genau die AK abgeschrieben sind
        voll = ak - summe if i == ELEKTRO_JAHRE - 1 else _div_round(ak * anteil, 10000)
        afa = _div_round(voll * abgang[1], 12) if abgang and abgang[0] == jahr else voll
        zeilen.append({"jahr": jahr, "afa_cent": afa, "linear": False})
        summe += voll
    return zeilen


def _schedule_sammelposten(ak: int, datum: str) -> list[dict]:
    y0, _ = _parse_ym(datum)
    zeilen, summe = [], 0
    for i in range(SAMMELPOSTEN_JAHRE):
        afa = ak - summe if i == SAMMELPOSTEN_JAHRE - 1 else _div_round(ak, SAMMELPOSTEN_JAHRE)
        zeilen.append({"jahr": y0 + i, "afa_cent": afa, "linear": False})
        summe += afa
    return zeilen


def verlauf(
    anschaffungskosten_cent: int,
    anschaffungsdatum: str,
    nutzungsdauer_jahre: int,
    methode: str = "linear",
    degressiv_bp: int | None = None,
    linear_ab_jahr: int | None = None,
    abgang_datum: str | None = None,
) -> list[dict]:
    """AfA-Plan je Jahr: [{jahr, afa_cent, buchwert_cent, linear}] — Buchwert zum Jahresende."""
    ak, datum = anschaffungskosten_cent, anschaffungsdatum
    if methode == "degressiv":
        zeilen = _schedule_degressiv(ak, datum, nutzungsdauer_jahre, degressiv_bp or 0, linear_ab_jahr, abgang_datum)
    elif methode == "elektro":
        zeilen = _schedule_elektro(ak, datum, abgang_datum)
    elif methode == "sammelposten":
        zeilen = _schedule_sammelposten(ak, datum)  # Abgang ändert nichts
    else:
        y0, _ = _parse_ym(datum)
        letzter = y0 + max(nutzungsdauer_jahre, 1)
        zeilen = [
            {"jahr": y, "afa_cent": _linear_jahr_cent(ak, datum, nutzungsdauer_jahre, y, abgang_datum), "linear": True}
            for y in range(y0, letzter + 1)
        ]
        zeilen = [z for z in zeilen if z["afa_cent"] != 0]
    buchwert = ak
    for z in zeilen:
        buchwert -= z["afa_cent"]
        z["buchwert_cent"] = buchwert
    return zeilen


def jahres_afa_cent(
    anschaffungskosten_cent: int,
    anschaffungsdatum: str,
    nutzungsdauer_jahre: int,
    jahr: int,
    abgang_datum: str | None = None,
    methode: str = "linear",
    degressiv_bp: int | None = None,
    linear_ab_jahr: int | None = None,
) -> int:
    """AfA-Betrag (Cent) eines Wirtschaftsguts für ein bestimmtes Kalenderjahr."""
    if methode == "linear" or methode is None:
        return _linear_jahr_cent(anschaffungskosten_cent, anschaffungsdatum, nutzungsdauer_jahre, jahr, abgang_datum)
    for z in verlauf(anschaffungskosten_cent, anschaffungsdatum, nutzungsdauer_jahre, methode, degressiv_bp,
                     linear_ab_jahr, abgang_datum):
        if z["jahr"] == jahr:
            return z["afa_cent"]
    return 0


def restbuchwert_cent(
    anschaffungskosten_cent: int,
    anschaffungsdatum: str,
    nutzungsdauer_jahre: int,
    abgang_datum: str | None,
    methode: str = "linear",
    degressiv_bp: int | None = None,
    linear_ab_jahr: int | None = None,
) -> int:
    """Restbuchwert zum Abgang (Cent). Ohne Abgang, bei Sofort-Option und beim Sammelposten (der Pool läuft
    weiter) ist er 0."""
    if methode == "linear" or methode is None:
        return _linear_restbuchwert_cent(anschaffungskosten_cent, anschaffungsdatum, nutzungsdauer_jahre, abgang_datum)
    if not abgang_datum or methode == "sammelposten":
        return 0
    zeilen = verlauf(anschaffungskosten_cent, anschaffungsdatum, nutzungsdauer_jahre, methode, degressiv_bp,
                     linear_ab_jahr, abgang_datum)
    return anschaffungskosten_cent - sum(z["afa_cent"] for z in zeilen)


def afa_jahr(a, jahr: int) -> int:
    """Jahres-AfA einer afa_buchung-Zeile (Row/dict mit den AfA-Spalten)."""
    return jahres_afa_cent(
        a["anschaffungskosten_cent"], a["anschaffungsdatum"], a["nutzungsdauer_jahre"], jahr, a["abgang_datum"],
        a["afa_methode"], a["degressiv_bp"], a["linear_ab_jahr"],
    )


def afa_restbuchwert(a) -> int:
    return restbuchwert_cent(
        a["anschaffungskosten_cent"], a["anschaffungsdatum"], a["nutzungsdauer_jahre"], a["abgang_datum"],
        a["afa_methode"], a["degressiv_bp"], a["linear_ab_jahr"],
    )


def methode_text(a) -> str:
    """Kurzbeschreibung für Journal und Listen: 'degressiv 30 %', 'Elektro-Staffel', …"""
    m = a["afa_methode"] or "linear"
    if m == "degressiv":
        text = f"degressiv {_prozent(a['degressiv_bp'] or 0)} %"
        return text + (f", linear ab {a['linear_ab_jahr']}" if a["linear_ab_jahr"] else "")
    return {"elektro": "Elektro-Staffel 75/10/5/5/3/2 %", "sammelposten": "Sammelposten 1/5 je Jahr"}.get(m, "linear")
