"""Mahnung als PDF (fpdf2, Core-Font — Umlaute ok, Beträge als „EUR“).

Gleicher Briefbogen wie die Rechnung (Absenderzeile, Empfänger, Meta-Block), dann Titel
mit Bezug zur Rechnung, Einleitung, Rechnungszeile, Forderungsaufstellung, Zahlungs-
aufforderung mit IBAN und Schluss. Entwurf: „ENTWURF“ quer über der Seite.
Alle Werte kommen fertig aus dem Mahnung-Schnappschuss — hier wird nichts berechnet.
"""
from __future__ import annotations

import sqlite3

from fpdf import FPDF

from .export import _date_de, format_cent_de
from .girocode import (
    GIRO_MM,
    absender_name,
    epc_payload,
    kontoinhaber,
    zeichne_platzhalter,
    zeichne_qr,
)
from .mahnwesen import STUFEN, effektive_faelligkeit
from .rechnung_pdf import INK, LINE, MUTED, ROYAL, latin1 as _t
from .logo import zeichne_logo


def _prozent(bp: int) -> str:
    return f"{bp / 100:.2f}".replace(".", ",") + " %"


def build_mahnung_pdf(
    mahnung: dict,
    rechnung: sqlite3.Row | dict,
    gewerbe: sqlite3.Row | dict,
    *,
    entwurf: bool = False,
) -> bytes:
    stufe = STUFEN[mahnung["stufe"]]
    pdf = FPDF(format="A4")
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(left=22, top=18, right=20)
    pdf.add_page()
    zeichne_logo(pdf, gewerbe)

    if entwurf:
        with pdf.rotation(angle=40, x=105, y=150):
            pdf.set_font("helvetica", "B", 84)
            pdf.set_text_color(232, 234, 240)
            pdf.text(28, 160, "ENTWURF")

    # Absenderzeile klein (Fensterumschlag-Stil)
    absender_block = (gewerbe["anschrift"] or gewerbe["name"] or "").strip()
    absender_einzeilig = " · ".join(z.strip() for z in absender_block.splitlines() if z.strip())
    pdf.set_font("helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 4, _t(absender_einzeilig), new_x="LMARGIN", new_y="NEXT")
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
    pdf.multi_cell(95, 5.2, _t(empf))

    pdf.set_xy(135, y_start)
    meta = [("Datum", _date_de(mahnung["datum"])), ("Rechnungsnummer", rechnung["nummer"])]
    for label, wert in meta:
        pdf.set_xy(120, pdf.get_y())
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(32, 4.6, label)
        pdf.set_font("helvetica", "", 9.5)
        pdf.set_text_color(*INK)
        pdf.cell(0, 4.6, _t(str(wert)), new_x="LMARGIN", new_y="NEXT")
    pdf.set_y(max(pdf.get_y(), y_start + 30) + 10)

    # Titel + Bezug
    pdf.set_font("helvetica", "B", 16)
    pdf.set_text_color(*INK)
    pdf.cell(0, 8, _t(stufe["titel"]), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("helvetica", "", 9.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(
        0, 5, _t(f"zur Rechnung {rechnung['nummer']} vom {_date_de(rechnung['datum'])}"),
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(5)

    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.cell(0, 5.4, "Sehr geehrte Damen und Herren,", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.multi_cell(0, 5.4, _t(mahnung["einleitung"]), align="L")
    pdf.ln(4)

    # Rechnungszeile
    w1, w2, w3, w4 = 66, 34, 34, 34
    pdf.set_font("helvetica", "B", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(w1, 6, "RECHNUNG")
    pdf.cell(w2, 6, "RECHNUNGSDATUM", align="R")
    pdf.cell(w3, 6, "FÄLLIG SEIT", align="R")
    pdf.cell(w4, 6, "OFFEN", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*INK)
    pdf.line(22, pdf.get_y(), 190, pdf.get_y())
    pdf.ln(1.5)
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.cell(w1, 6, _t(rechnung["nummer"]))
    pdf.cell(w2, 6, _date_de(rechnung["datum"]), align="R")
    pdf.cell(w3, 6, _date_de(effektive_faelligkeit(rechnung["datum"], rechnung["faellig_am"])),
             align="R")
    pdf.cell(w4, 6, format_cent_de(mahnung["offen_cent"]) + " EUR", align="R",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*LINE)
    pdf.line(22, pdf.get_y() + 0.5, 190, pdf.get_y() + 0.5)
    pdf.ln(5)

    # Forderungsaufstellung (rechtsbündiger Block)
    zeilen = [("Offener Rechnungsbetrag", mahnung["offen_cent"])]
    if mahnung["gebuehr_cent"]:
        label = "Mahngebühr, soweit über der Pauschale" if mahnung["pauschale_cent"] else "Mahngebühr"
        zeilen.append((label, mahnung["gebuehr_cent"]))
    if mahnung["pauschale_cent"]:
        zeilen.append(("Verzugspauschale (§ 288 Abs. 5 BGB)", mahnung["pauschale_cent"]))
    if mahnung["zinsen_cent"]:
        zeilen.append(
            (
                f"Verzugszinsen {_prozent(mahnung['zinssatz_bp'])} p. a. für {mahnung['zinstage']} Tage",
                mahnung["zinsen_cent"],
            )
        )
    x0, wl, wr = 98, 62, 30
    pdf.set_font("helvetica", "", 9.5)
    for label, cent in zeilen:
        pdf.set_x(x0)
        pdf.set_text_color(*MUTED)
        pdf.cell(wl, 6, _t(label))
        pdf.set_text_color(*INK)
        pdf.cell(wr, 6, format_cent_de(cent) + " EUR", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_draw_color(*ROYAL)
    pdf.line(x0, pdf.get_y() + 1, 190, pdf.get_y() + 1)
    pdf.ln(2.5)
    pdf.set_x(x0)
    pdf.set_font("helvetica", "B", 11.5)
    pdf.set_text_color(*INK)
    pdf.cell(wl, 7, "Zu zahlen")
    pdf.set_text_color(*ROYAL)
    pdf.cell(wr, 7, format_cent_de(mahnung["gesamt_cent"]) + " EUR", align="R",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # Zahlungsaufforderung — rechts daneben der GiroCode über den Gesamtbetrag (im Entwurf nur ein
    # Platzhalter: ein Entwurf soll nicht bezahlt werden)
    giro = epc_payload(
        name=kontoinhaber(gewerbe),
        iban=gewerbe["iban"],
        betrag_cent=mahnung["gesamt_cent"],
        verwendungszweck=f"Rechnung {rechnung['nummer']}",
    )
    if giro and pdf.get_y() + GIRO_MM + 2 > 272:
        pdf.add_page()
    y_zahlung = pdf.get_y()
    if giro:
        if entwurf:
            zeichne_platzhalter(pdf, 190 - GIRO_MM, y_zahlung)
        else:
            zeichne_qr(pdf, giro, 190 - GIRO_MM, y_zahlung)
        pdf.set_xy(22, y_zahlung)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(*INK)
    konto = f" auf das Konto IBAN {gewerbe['iban']}" if gewerbe["iban"] else ""
    pdf.multi_cell(
        135 if giro else 0, 5.4,
        _t(
            f"Bitte überweisen Sie {format_cent_de(mahnung['gesamt_cent'])} EUR bis zum "
            f"{_date_de(mahnung['frist_am'])}{konto} unter Angabe der Rechnungsnummer "
            f"{rechnung['nummer']}."
            + (" Das Skonto aus der Rechnung ist mit Ablauf der Skontofrist entfallen." if rechnung["skonto_bp"] else "")
        ),
        align="L",
    )
    if giro:
        pdf.set_y(max(pdf.get_y(), y_zahlung + GIRO_MM + 1))
    pdf.ln(3)
    pdf.set_font("helvetica", "", 10)
    if (mahnung["schluss"] or "").strip():
        pdf.multi_cell(0, 5.4, _t(mahnung["schluss"].strip()), align="L")
        pdf.ln(3)
    pdf.ln(2)
    pdf.cell(0, 5.4, "Mit freundlichen Grüßen", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5.4, _t(absender_name(gewerbe)), new_x="LMARGIN", new_y="NEXT")

    if gewerbe["rechnung_fusszeile"]:
        pdf.ln(6)
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(*MUTED)
        for zeile in gewerbe["rechnung_fusszeile"].splitlines():
            pdf.cell(0, 4.8, _t(zeile), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
