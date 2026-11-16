"""E-Rechnung (ZUGFeRD/Factur-X, Profil EN 16931): unsere normale PDF-Rechnung
bekommt das maschinenlesbare CII-XML eingebettet (PDF/A-3 via factur-x-Lib).
Menschliche Empfänger merken nichts, Buchhaltungssoftware liest die Daten.

KU-Fall: keine USt — Steuerkategorie „E" (exempt) mit dem gewählten Steuer-
Hinweis als Befreiungsgrund. B2G/Leitweg-ID ist bewusst außen vor.
Schlägt das Einbetten fehl, liefert `rechnungs_pdf` die normale PDF —
E-Rechnung darf Versand/Download nie blockieren.
"""
from __future__ import annotations

import logging
import re
import sqlite3
from xml.sax.saxutils import escape

from . import rechnung_summen
from .rechnung_pdf import STEUERHINWEISE, build_rechnung_pdf

log = logging.getLogger("tab.e_rechnung")


def _eur(cent: int) -> str:
    sign = "-" if cent < 0 else ""
    v = abs(int(cent))
    return f"{sign}{v // 100}.{v % 100:02d}"


def _menge(m: float) -> str:
    return str(int(m)) if float(m) == int(m) else f"{m}"


def _datum_102(iso: str) -> str:
    return iso[:10].replace("-", "")


def _datum_de(iso: str) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


def parse_anschrift(text: str | None) -> dict:
    """Freitext-Anschrift tolerant zerlegen: erste Zeile = Name, Zeile vor der
    PLZ-Zeile = Straße, PLZ/Ort per Muster. Fehlt etwas, bleibt es leer."""
    zeilen = [z.strip() for z in (text or "").splitlines() if z.strip()]
    name = zeilen[0] if zeilen else None
    strasse = plz = ort = None
    for i, z in enumerate(zeilen):
        m = re.match(r"^(\d{5})\s+(.+)$", z)
        if m:
            plz, ort = m.group(1), m.group(2)
            if i >= 1:
                strasse = zeilen[i - 1]
            break
    return {"name": name, "strasse": strasse, "plz": plz, "ort": ort}


def _adresse_xml(a: dict) -> str:
    teile = []
    if a.get("plz"):
        teile.append(f"<ram:PostcodeCode>{escape(a['plz'])}</ram:PostcodeCode>")
    if a.get("strasse"):
        teile.append(f"<ram:LineOne>{escape(a['strasse'])}</ram:LineOne>")
    if a.get("ort"):
        teile.append(f"<ram:CityName>{escape(a['ort'])}</ram:CityName>")
    teile.append("<ram:CountryID>DE</ram:CountryID>")
    return "<ram:PostalTradeAddress>" + "".join(teile) + "</ram:PostalTradeAddress>"


def zugferd_xml(rechnung, positionen, gewerbe) -> bytes:
    """EN-16931-CII-XML. Kleinunternehmer: alles Kategorie E (0 %, Grund = Steuerhinweis) wie bisher.
    Regelbesteuerung: Kategorie S je Satz, Positionen ohne USt Kategorie E mit dem Steuerhinweis als Grund;
    Steuer je Satz auf die Netto-Summe (services/rechnung_summen)."""
    hinweis = STEUERHINWEISE.get(rechnung["steuerhinweis"], STEUERHINWEISE["ku19"])
    sm = rechnung_summen.summen(positionen)
    mit_ust = sm["mit_ust"]
    summe = sm["netto_cent"]

    def _satz(p) -> int:
        try:
            return p["ust_bp"] or 0
        except (KeyError, IndexError):
            return 0

    def _steuer_zeile(satz: int) -> str:
        if mit_ust and satz:
            return (f"<ram:TypeCode>VAT</ram:TypeCode>\n          <ram:CategoryCode>S</ram:CategoryCode>\n"
                    f"          <ram:RateApplicablePercent>{satz / 100:.2f}</ram:RateApplicablePercent>")
        return ("<ram:TypeCode>VAT</ram:TypeCode>\n          <ram:CategoryCode>E</ram:CategoryCode>\n"
                "          <ram:RateApplicablePercent>0.00</ram:RateApplicablePercent>")

    zeilen_xml = []
    for i, p in enumerate(positionen, start=1):
        line_total = rechnung_summen.zeile_netto(p["menge"], p["einzelpreis_cent"])
        zeilen_xml.append(f"""
    <ram:IncludedSupplyChainTradeLineItem>
      <ram:AssociatedDocumentLineDocument><ram:LineID>{i}</ram:LineID></ram:AssociatedDocumentLineDocument>
      <ram:SpecifiedTradeProduct><ram:Name>{escape(p["beschreibung"])}</ram:Name></ram:SpecifiedTradeProduct>
      <ram:SpecifiedLineTradeAgreement>
        <ram:NetPriceProductTradePrice><ram:ChargeAmount>{_eur(p["einzelpreis_cent"])}</ram:ChargeAmount></ram:NetPriceProductTradePrice>
      </ram:SpecifiedLineTradeAgreement>
      <ram:SpecifiedLineTradeDelivery>
        <ram:BilledQuantity unitCode="C62">{_menge(p["menge"])}</ram:BilledQuantity>
      </ram:SpecifiedLineTradeDelivery>
      <ram:SpecifiedLineTradeSettlement>
        <ram:ApplicableTradeTax>
          {_steuer_zeile(_satz(p))}
        </ram:ApplicableTradeTax>
        <ram:SpecifiedTradeSettlementLineMonetarySummation>
          <ram:LineTotalAmount>{_eur(line_total)}</ram:LineTotalAmount>
        </ram:SpecifiedTradeSettlementLineMonetarySummation>
      </ram:SpecifiedLineTradeSettlement>
    </ram:IncludedSupplyChainTradeLineItem>""")

    verkaeufer = parse_anschrift(gewerbe["anschrift"])
    verkaeufer_name = verkaeufer["name"] or gewerbe["name"]
    kaeufer = parse_anschrift(
        (rechnung["empfaenger_name"] or "") + "\n" + (rechnung["empfaenger_anschrift"] or "")
    )
    kaeufer["name"] = rechnung["empfaenger_name"]

    # BT-13: Bestellreferenz des Käufers (steht auch im PDF als „Ihre Bestellnr.")
    bestell_xml = ""
    bestellnummer = (rechnung["bestellnummer"] if "bestellnummer" in rechnung.keys() else None) or ""
    if bestellnummer.strip():
        bestell_xml = (
            "\n      <ram:BuyerOrderReferencedDocument>"
            f"<ram:IssuerAssignedID>{escape(bestellnummer.strip())}</ram:IssuerAssignedID>"
            "</ram:BuyerOrderReferencedDocument>"
        )

    steuernr_xml = ""
    if gewerbe["steuernummer"]:
        steuernr_xml = (
            "<ram:SpecifiedTaxRegistration>"
            f'<ram:ID schemeID="FC">{escape(gewerbe["steuernummer"])}</ram:ID>'
            "</ram:SpecifiedTaxRegistration>"
        )
    ust_id = (gewerbe["ust_id"] if "ust_id" in gewerbe.keys() else None) or ""
    if ust_id.strip():
        # BT-31 USt-IdNr. des Verkäufers
        steuernr_xml += (
            "<ram:SpecifiedTaxRegistration>"
            f'<ram:ID schemeID="VA">{escape(ust_id.strip())}</ram:ID>'
            "</ram:SpecifiedTaxRegistration>"
        )

    # Steuer im Kopf: KU genau wie bisher eine E-Gruppe; Regelbesteuerung je Satz eine Gruppe
    if mit_ust:
        gruppen = []
        for g in sm["je_satz"]:
            if g["ust_bp"]:
                gruppen.append(f"""
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>{_eur(g["ust_cent"])}</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:BasisAmount>{_eur(g["netto_cent"])}</ram:BasisAmount>
        <ram:CategoryCode>S</ram:CategoryCode>
        <ram:RateApplicablePercent>{g["ust_bp"] / 100:.2f}</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>""")
            else:
                gruppen.append(f"""
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>0.00</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:ExemptionReason>{escape(hinweis or "Steuerfreie Leistung")}</ram:ExemptionReason>
        <ram:BasisAmount>{_eur(g["netto_cent"])}</ram:BasisAmount>
        <ram:CategoryCode>E</ram:CategoryCode>
        <ram:RateApplicablePercent>0.00</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>""")
        steuer_xml = "".join(gruppen)
    else:
        steuer_xml = f"""
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>0.00</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:ExemptionReason>{escape(hinweis)}</ram:ExemptionReason>
        <ram:BasisAmount>{_eur(summe)}</ram:BasisAmount>
        <ram:CategoryCode>E</ram:CategoryCode>
        <ram:RateApplicablePercent>0.00</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>"""
    hinweis_xml = f"\n    <ram:IncludedNote><ram:Content>{escape(hinweis)}</ram:Content></ram:IncludedNote>" if hinweis else ""

    zahlung_xml = ""
    if gewerbe["iban"]:
        iban = gewerbe["iban"].replace(" ", "")
        # Name des Zahlungskontos (BT-85) nur, wenn ein Kontoinhaber ausdrücklich hinterlegt ist
        konto_name = (gewerbe["kontoinhaber"] or "").strip()
        konto_name_xml = f"<ram:AccountName>{escape(konto_name)}</ram:AccountName>" if konto_name else ""
        zahlung_xml = f"""
      <ram:SpecifiedTradeSettlementPaymentMeans>
        <ram:TypeCode>58</ram:TypeCode>
        <ram:PayeePartyCreditorFinancialAccount><ram:IBANID>{escape(iban)}</ram:IBANID>{konto_name_xml}</ram:PayeePartyCreditorFinancialAccount>
      </ram:SpecifiedTradeSettlementPaymentMeans>"""

    # Fälligkeit (BT-9) + Zahlungsbedingungen: Pflicht, wenn ein Betrag zu zahlen ist (BR-CO-25).
    zahlungsbedingungen_xml = ""
    # Skonto maschinenlesbar im Format der XRechnung (BR-DE-18): #SKONTO#TAGE=10#PROZENT=2.00#
    skonto_zeile = ""
    if rechnung["skonto_bp"] and rechnung["skonto_tage"]:
        skonto_zeile = f"\n#SKONTO#TAGE={rechnung['skonto_tage']}#PROZENT={rechnung['skonto_bp'] / 100:.2f}#"
    if rechnung["faellig_am"]:
        zahlungsbedingungen_xml = (
            "\n      <ram:SpecifiedTradePaymentTerms>"
            f"<ram:Description>Zahlbar bis zum {_datum_de(rechnung['faellig_am'])}.{skonto_zeile}</ram:Description>"
            '<ram:DueDateDateTime><udt:DateTimeString format="102">'
            f"{_datum_102(rechnung['faellig_am'])}</udt:DateTimeString></ram:DueDateDateTime>"
            "</ram:SpecifiedTradePaymentTerms>"
        )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice
  xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
  xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
  xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>{escape(rechnung["nummer"])}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime><udt:DateTimeString format="102">{_datum_102(rechnung["datum"])}</udt:DateTimeString></ram:IssueDateTime>{hinweis_xml}
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>{"".join(zeilen_xml)}
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>{escape(verkaeufer_name)}</ram:Name>
        {_adresse_xml(verkaeufer)}
        {steuernr_xml}
      </ram:SellerTradeParty>
      <ram:BuyerTradeParty>
        <ram:Name>{escape(kaeufer["name"])}</ram:Name>
        {_adresse_xml(kaeufer)}
      </ram:BuyerTradeParty>{bestell_xml}
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeDelivery/>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>{zahlung_xml}{steuer_xml}{zahlungsbedingungen_xml}
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:LineTotalAmount>{_eur(summe)}</ram:LineTotalAmount>
        <ram:TaxBasisTotalAmount>{_eur(summe)}</ram:TaxBasisTotalAmount>
        <ram:TaxTotalAmount currencyID="EUR">{_eur(sm["ust_cent"])}</ram:TaxTotalAmount>
        <ram:GrandTotalAmount>{_eur(sm["brutto_cent"])}</ram:GrandTotalAmount>
        <ram:DuePayableAmount>{_eur(sm["brutto_cent"])}</ram:DuePayableAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""
    return xml.encode("utf-8")


def rechnungs_pdf(rechnung, positionen, gewerbe: sqlite3.Row | dict) -> bytes:
    """Sicht-PDF bauen und (best effort) als ZUGFeRD-E-Rechnung anreichern."""
    pdf = build_rechnung_pdf(rechnung, positionen, gewerbe)
    try:
        try:
            from facturx import generate_from_binary
        except ImportError:  # ältere factur-x-Versionen
            from facturx import generate_facturx_from_binary as generate_from_binary

        xml = zugferd_xml(rechnung, positionen, gewerbe)
        return generate_from_binary(pdf, xml, check_xsd=True)
    except Exception:
        log.exception("ZUGFeRD-Einbettung fehlgeschlagen — liefere normale PDF (Rechnung %s)",
                      rechnung["nummer"])
        return pdf
