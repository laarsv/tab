"""Angebots-PDF (fpdf2, Core-Font Latin-1) — gleicher Briefbogen wie die Rechnung.

Positionen sind „normal“ (zählen zur Angebotssumme) oder „optional“ (Zusatzleistung, die der Kunde
dazu bestellen kann; mit Preis, aber nicht in der Summe). Entwurf: „ENTWURF“ quer über der Seite.
"""
from __future__ import annotations

import sqlite3

from fpdf import FPDF
from fpdf.enums import MethodReturnValue

from .export import _date_de, format_cent_de
from .girocode import absender_name
from .rechnung_pdf import INK, LINE, MUTED, ROYAL, STEUERHINWEISE, _menge_de, latin1


def build_angebot_pdf(
    angebot: sqlite3.Row | dict,
    positionen: list,
    gewerbe: sqlite3.Row | dict,
    *,
    entwurf: bool = False,
) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(left=22, top=18, right=20)
    pdf.add_page()

    if entwurf:
        with pdf.rotation(angle=40, x=105, y=150):
            pdf.set_font("helvetica", "B", 84)
            pdf.set_text_color(232, 234, 240)
            pdf.text(28, 160, "ENTWURF")

    # Absenderzeile klein (Fensterumschlag-Stil)
    block = (gewerbe["anschrift"] or gewerbe["name"] or "").strip()
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, latin1(" · ".join(z.strip() for z in block.splitlines() if z.strip())), new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(22, pdf.get_y() + 0.5, 120, pdf.get_y() + 0.5)
    pdf.ln(6)

    # Empfänger links, Meta rechts
    y_start = pdf.get_y()
    pdf.set_font("helvetica", "", 10.5)
    pdf.set_text_color(*INK)
    empf = angebot["empfaenger_name"] + ("\n" + angebot["empfaenger_anschrift"] if angebot["empfaenger_anschrift"] else "")
    pdf.multi_cell(95, 5.2, latin1(empf))
    pdf.set_xy(135, y_start)
    meta = [
        ("Angebotsnummer", angebot["nummer"]),
        ("Angebotsdatum", _date_de(angebot["datum"])),
        ("Gültig bis", _date_de(angebot["gueltig_bis"])),
    ]
    if gewerbe["steuernummer"]:
        meta.append(("Steuernummer", gewerbe["steuernummer"]))
    for label, wert in meta:
        pdf.set_xy(120, pdf.get_y())
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(32, 4.6, latin1(label))
        pdf.set_font("helvetica", "", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(0, 4.6, latin1(str(wert)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(max(pdf.get_y(), y_start + 34) + 10)

    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, latin1(f"Angebot {angebot['nummer']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("helvetica", "", 10)
    pdf.cell(0, 5.4, "Sehr geehrte Damen und Herren,", new_x="LMARGIN", new_y="NEXT")
    if (angebot["einleitung"] or "").strip():
        pdf.ln(2)
        pdf.multi_cell(0, 5.4, latin1(angebot["einleitung"].strip()), align="L")
    pdf.ln(4)

    # Positionen
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

    summe = optional = 0
    for p in positionen:
        betrag = round(p["menge"] * p["einzelpreis_cent"])
        ist_optional = p["art"] == "optional"
        if ist_optional:
            optional += betrag
        else:
            summe += betrag
        text = latin1(p["beschreibung"]) + ("\nOptional, nicht in der Angebotssumme" if ist_optional else "")
        pdf.set_font("helvetica", "", 10)
        zeilen = len(pdf.multi_cell(w_pos, 5.4, text, dry_run=True, output=MethodReturnValue.LINES))
        if pdf.get_y() + max(5.4, zeilen * 5.4) + 3 > pdf.page_break_trigger:
            pdf.add_page()
        y0 = pdf.get_y()
        pdf.set_text_color(*(MUTED if ist_optional else INK))
        pdf.multi_cell(w_pos, 5.4, text)
        y1 = pdf.get_y()
        pdf.set_xy(22 + w_pos, y0)
        pdf.cell(w_menge, 5.4, _menge_de(p["menge"]), align="R")
        pdf.cell(w_preis, 5.4, format_cent_de(p["einzelpreis_cent"]) + " EUR", align="R")
        pdf.cell(w_summe, 5.4, format_cent_de(betrag) + " EUR", align="R")
        pdf.set_y(max(y0 + 5.4, y1) + 1.5)
        pdf.set_draw_color(*LINE)
        pdf.line(22, pdf.get_y(), 190, pdf.get_y())
        pdf.ln(1.5)

    pdf.ln(2)
    pdf.set_font("helvetica", "B", 11.5)
    pdf.set_text_color(*INK)
    pdf.cell(w_pos, 7, "")
    pdf.cell(w_menge + w_preis, 7, "Angebotssumme", align="R")
    pdf.set_text_color(*ROYAL)
    pdf.cell(w_summe, 7, format_cent_de(summe) + " EUR", align="R", new_x="LMARGIN", new_y="NEXT")
    if optional:
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 5, f"Optionale Positionen zusätzlich: {format_cent_de(optional)} EUR", align="R",
                 new_x="LMARGIN", new_y="NEXT")

    pdf.ln(3)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 5, STEUERHINWEISE.get(angebot["steuerhinweis"], STEUERHINWEISE["ku19"]))
    if (angebot["notiz"] or "").strip():
        pdf.ln(3)
        pdf.set_font("helvetica", "", 10)
        pdf.set_text_color(*INK)
        pdf.multi_cell(0, 5.4, latin1(angebot["notiz"].strip()), align="L")
    pdf.ln(4)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.cell(0, 5.4, f"Dieses Angebot ist gültig bis zum {_date_de(angebot['gueltig_bis'])}.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    pdf.cell(0, 5.4, "Mit freundlichen Grüßen", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5.4, latin1(absender_name(gewerbe)), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
