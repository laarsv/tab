"""Rechnungs-PDF (fpdf2, Core-Font Helvetica/Latin-1 — Umlaute ok, Beträge als „EUR",
da € nicht im Font).

Schlichtes A4-Layout mit allen KU-Pflichtangaben: Absender (Gewerbe-Anschrift),
Empfänger, Rechnungsnummer, Datum, Leistungsdatum, Positionen, Summe ohne USt +
§19-Hinweis, Zahlungsinfo (IBAN/Fußzeile).
"""
from __future__ import annotations

import sqlite3

from fpdf import FPDF

from .export import format_cent_de, _date_de

INK = (22, 26, 36)       # ink
MUTED = (110, 115, 125)
ROYAL = (41, 71, 201)    # royal
LINE = (225, 228, 235)

P19_HINWEIS = "Kein Ausweis von Umsatzsteuer, da Kleinunternehmer gemäß § 19 UStG."


def _menge_de(menge: float) -> str:
    if float(menge) == int(menge):
        return str(int(menge))
    return f"{menge}".replace(".", ",")


def build_rechnung_pdf(
    rechnung: sqlite3.Row | dict,
    positionen: list,
    gewerbe: sqlite3.Row | dict,
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(left=22, top=18, right=20)
    pdf.add_page()

    # Absenderzeile klein (Fensterumschlag-Stil)
    absender_block = (gewerbe["anschrift"] or gewerbe["name"] or "").strip()
    absender_einzeilig = " · ".join(z.strip() for z in absender_block.splitlines() if z.strip())
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, absender_einzeilig, new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(22, pdf.get_y() + 0.5, 120, pdf.get_y() + 0.5)
    pdf.ln(6)

    # Empfänger links, Meta-Block rechts
    y_start = pdf.get_y()
    pdf.set_font("helvetica", "", 10.5)
    pdf.set_text_color(*INK)
    empf = rechnung["empfaenger_name"] + (
        "\n" + rechnung["empfaenger_anschrift"] if rechnung["empfaenger_anschrift"] else ""
    )
    pdf.multi_cell(95, 5.2, empf)

    pdf.set_xy(135, y_start)
    meta = [
        ("Rechnungsnummer", rechnung["nummer"]),
        ("Rechnungsdatum", _date_de(rechnung["datum"])),
        ("Leistungsdatum", rechnung["leistungsdatum"] or _date_de(rechnung["datum"])),
    ]
    if gewerbe["steuernummer"]:
        meta.append(("Steuernummer", gewerbe["steuernummer"]))
    for label, wert in meta:
        pdf.set_xy(120, pdf.get_y())
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(32, 4.6, label)
        pdf.set_font("helvetica", "", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(0, 4.6, str(wert), new_x="LMARGIN", new_y="NEXT")

    pdf.set_y(max(pdf.get_y(), y_start + 34) + 10)

    # Titel
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, f"Rechnung {rechnung['nummer']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Positionstabelle
    w_pos, w_menge, w_preis, w_summe = 96, 18, 27, 27
    pdf.set_font("helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(w_pos, 6, "LEISTUNG")
    pdf.cell(w_menge, 6, "MENGE", align="R")
    pdf.cell(w_preis, 6, "EINZELPREIS", align="R")
    pdf.cell(w_summe, 6, "BETRAG", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*INK)
    pdf.line(22, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(1.5)

    summe = 0
    pdf.set_text_color(*INK)
    for p in positionen:
        betrag = round(p["menge"] * p["einzelpreis_cent"])
        summe += betrag
        y0 = pdf.get_y()
        pdf.set_font("helvetica", "", 10)
        pdf.multi_cell(w_pos, 5.4, p["beschreibung"])
        y1 = pdf.get_y()
        pdf.set_xy(22 + w_pos, y0)
        pdf.cell(w_menge, 5.4, _menge_de(p["menge"]), align="R")
        pdf.cell(w_preis, 5.4, format_cent_de(p["einzelpreis_cent"]) + " EUR", align="R")
        pdf.cell(w_summe, 5.4, format_cent_de(betrag) + " EUR", align="R")
        pdf.set_y(max(y0 + 5.4, y1) + 1.5)
        pdf.set_draw_color(*LINE)
        pdf.line(22, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(1.5)

    # Summe
    pdf.ln(2)
    pdf.set_font("helvetica", "B", 11.5)
    pdf.cell(w_pos + w_menge, 7, "")
    pdf.cell(w_preis, 7, "Gesamtbetrag")
    pdf.set_text_color(*ROYAL)
    pdf.cell(w_summe, 7, format_cent_de(summe) + " EUR", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(*INK)

    # §19-Hinweis (Pflicht)
    pdf.ln(3)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 5, P19_HINWEIS, new_x="LMARGIN", new_y="NEXT")

    # Zahlungsinfo
    pdf.ln(6)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*INK)
    if gewerbe["iban"]:
        pdf.cell(0, 5.4, f"Bitte überweisen Sie den Betrag auf: IBAN {gewerbe['iban']}",
                 new_x="LMARGIN", new_y="NEXT")
    if gewerbe["rechnung_fusszeile"]:
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        for zeile in gewerbe["rechnung_fusszeile"].splitlines():
            pdf.cell(0, 4.8, zeile, new_x="LMARGIN", new_y="NEXT")
    if rechnung["notiz"]:
        pdf.ln(3)
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 5.4, rechnung["notiz"])

    return bytes(pdf.output())
