# Bilanzierung in Tab — fachliche Spezifikation

Stand 16.11.2026. Technische Spezifikation, **keine Steuerberatung**. Tab erstellt Bilanz und GuV als **prüfbaren
Entwurf** für die Steuerberatung; den Jahresabschluss und die E-Bilanz macht die Steuerberatung.

## 1. Wann

Einzelunternehmer mit Gewerbebetrieb ermitteln den Gewinn per EÜR (§ 4 Abs. 3 EStG), solange sie nicht buchführungspflichtig
sind. Pflicht entsteht nach § 141 AO, wenn Umsatz > 800.000 € oder Gewinn > 80.000 € im Wirtschaftsjahr — **erst ab dem
Wirtschaftsjahr nach der Mitteilung des Finanzamts**. Freiwillig geht immer. Tab: **Gewinnermittlung je Gewerbe und
Kalenderjahr** wählbar (`euer` | `bilanz`), Wechsel immer zum 1.1., nie für abgeschlossene Jahre. Ohne Eintrag EÜR.

## 2. Grundidee: ein abgeleitetes Journal

Tab führt kein zweites Hauptbuch. Für ein Bilanz-Jahr erzeugt `services/bilanz.py` aus den vorhandenen Daten ein internes
**doppeltes Journal** (jede Zeile Soll = Haben) und summiert es zu GuV und Bilanz. Dadurch geht die Bilanz immer auf; was
Tab nicht zuordnen kann, landet sichtbar auf dem **Verrechnungskonto** (Ziel: 0 €) und in der Abstimmung.

Interne Konten (Bestand): `anlage`, `bank:<konto_id>`, `kasse`, `forderungen` (Rechnungen und offene Einnahmen),
`forderungen_sonst`, `ara` (aktive RAP), `finanzamt` (USt/Vorsteuer, Regelbesteuerung), `verrechnung`,
`eigenkapital`, `privat` (Entnahmen −, Einlagen +; zum Jahresende ins Eigenkapital), `rueckstellungen`,
`verbindlichkeiten` (offene Ausgaben), `verb_sonst`, `pra` (passive RAP). Erfolg: `guv:<posten>`.

## 3. Woraus das Journal entsteht

| Quelle | Buchungssatz (Soll an Haben) | Datum |
|---|---|---|
| Eröffnung (nur erstes Bilanz-Jahr; danach Schlussbestand des Vorjahres) | Aktivposten an Eigenkapital / Eigenkapital an Passivposten | 1.1. |
| Ausgabe-Buchung | `guv:<posten>` (betrieblich, netto) + `finanzamt` (Vorsteuer) + `privat` (Privatanteil, brutto) an `verbindlichkeiten` | Rechnungsdatum (`rechnungsdatum`, sonst `datum`) |
| …ihre Zahlung | `verbindlichkeiten` an Zahlungskonto | Zahltag (`datum`, nicht bei `offen`) |
| Einnahme-Buchung (ohne Tab-Rechnung) | `forderungen` an `guv:<posten>` + `finanzamt` (USt) | Rechnungsdatum |
| …ihre Zahlung | Zahlungskonto an `forderungen` | Zahltag |
| Tab-Rechnung (versendet/bezahlt) | `forderungen` an `guv:umsatzerloese` (+ `finanzamt`) | Rechnungsdatum |
| Zahlung auf Tab-Rechnung (mit Buchung) | Zahlungskonto an `forderungen` | Zahltag |
| Skonto / Ausfall | `guv:erloesminderung` bzw. `guv:sonstige_aufwendungen` an `forderungen` | Tag |
| Anlage: Zugang | `anlage` (+ Vorsteuer) an `verrechnung` (die Zahlung ist ein ignorierter Bankumsatz) | Anschaffung |
| AfA | `guv:abschreibungen` an `anlage` | 31.12. |
| Restbuchwert-Buchung | `guv:sonstige_aufwendungen` an `anlage` | Tag |
| Bankumsatz ohne Buchung, „Privat“ | Bank an `privat` (Eingang) / `privat` an Bank (Abgang) | Umsatztag |
| …„ESt-Vorauszahlung“ | `privat` an Bank | |
| …„Gewerbesteuer“ | `guv:steuern_ertrag` an Bank (außerbilanziell hinzurechnen) | |
| …sonst (Umbuchung, Lohn, Anlage, offen) | Bank an `verrechnung` bzw. umgekehrt | |
| Abschlussbuchung | frei: Soll-Konto an Haben-Konto | eigenes Datum |

**Zahlungskonto:** das Bankkonto des verknüpften Umsatzes; Pauschalen ohne Geldfluss (km-, Entfernungs-,
Homeoffice-Pauschale, Verpflegungsmehraufwand) → `privat` (Einlage); Nutzungsentnahmen (1 %-Regelung, sonstige
Entnahmen) → `privat` (Entnahme); Restbuchwert → `anlage`; sonst `verrechnung`. Weicht der Umsatzbetrag vom
Buchungsbetrag ab, geht der Unterschied auf `verrechnung`.

Eine Buchung zählt in einem Bilanz-Jahr mit ihrer Rechnungs-Seite, wenn das Rechnungsdatum im Jahr liegt, und mit ihrer
Zahlungs-Seite, wenn der Zahltag im Jahr liegt. **Offene Buchungen** (`offen = 1`, noch nicht bezahlt) gibt es nur in
Bilanz-Jahren; beim Verknüpfen mit dem Bankumsatz wird `offen = 0` und `datum` = Zahltag.

## 4. GuV (Gesamtkostenverfahren, § 275 Abs. 2 HGB, verkürzt)

| GuV-Posten | Tab-Kategorien |
|---|---|
| 1. Umsatzerlöse | einnahme_ku, einnahme_ust, einnahme_steuerfrei, Tab-Rechnungen |
| 4. Sonstige betriebliche Erträge | veraeusserung_av, kfz_privatnutzung, entnahme_sonstig |
| 5a. Materialaufwand Waren | waren |
| 5b. Bezogene Leistungen | fremdleistungen |
| 6. Personalaufwand | personal |
| 7. Abschreibungen | AfA (berechnet), gwg |
| 8. Sonstige betriebliche Aufwendungen | alle übrigen Ausgabe-Kategorien, restbuchwert, Skonto/Ausfall |
| 13. Zinsen und ähnliche Aufwendungen | zinsen |
| 14. Steuern vom Einkommen und Ertrag | Gewerbesteuer (aus Bankumsätzen mit Grund „Gewerbesteuer“) |
| 17. Jahresüberschuss | Summe |

Nicht in der GuV: `ust_zahlung`, `ust_erstattung` (gegen `finanzamt`). Die Bewirtung steht voll in der GuV; die 30 % und
die Gewerbesteuer weist Tab als **außerbilanzielle Hinzurechnung** zum steuerlichen Gewinn aus.

## 5. Bilanz (verkürzt nach § 266 HGB)

Aktiva: A. Anlagevermögen (Sachanlagen) — B. Umlaufvermögen: Forderungen aus L+L, sonstige Vermögensgegenstände
(inkl. Finanzamt mit Guthaben), Kasse/Bank — C. Rechnungsabgrenzung. Passiva: A. Eigenkapital (Anfang, Einlagen,
Entnahmen, Jahresüberschuss, Ende) — B. Rückstellungen — C. Verbindlichkeiten aus L+L, sonstige (inkl. Finanzamt,
Verrechnung bei Habensaldo) — D. Rechnungsabgrenzung. Bankkonten mit Minussaldo und das Verrechnungskonto stehen auf
der Seite, auf die ihr Saldo gehört.

## 6. Eröffnung und Übergang EÜR → Bilanz

Erstes Bilanz-Jahr: Eröffnungswerte je Posten (Kontostände laut Auszug zum 31.12., Kasse, offene Verbindlichkeiten,
sonstige). Tab schlägt vor: Anlagen-Buchwerte (`services/afa.verlauf`), offene Tab-Rechnungen zum Stichtag, Bank =
leer (Kontostand kennt Tab nicht — vom Auszug abtippen). Eigenkapital = Aktiva − Passiva. **Übergangsgewinn** (R 4.6
EStR, vereinfacht) = Forderungen + aktive RAP − Verbindlichkeiten − Rückstellungen − passive RAP der Eröffnung; Tab zeigt
ihn als Hinweis, er gehört nicht in die GuV (Verteilung bis zu 3 Jahre auf Antrag).

Folgejahre: Eröffnung = Schlussbilanz des Vorjahres (Bilanzidentität), keine Eingabe.

## 7. Umsetzung (Stand v41)

- `services/bilanz.py`: `journal()`, `eroeffnung()`/`schluss()`, `auswertung()`, `eroeffnung_vorschlag()`, `csv_text()`.
- Zahlungsseite: Buchung bezahlt → `verrechnung` an `forderungen` bzw. `verbindlichkeiten` an `verrechnung`; jeder Bankumsatz
  → Bank an `verrechnung` (bzw. umgekehrt). Verknüpfte Paare heben sich auf dem Verrechnungskonto auf.
- Verbindlichkeiten aus der Eröffnung: Zahlung als ignorierten Umsatz („Umbuchung“) + Abschlussbuchung
  „Verbindlichkeiten an Verrechnung“ (Vorlage auf der Seite), sonst zählte die Ausgabe doppelt.
- Rückstellungen löst der Nutzer im Folgejahr per Abschlussbuchung auf (Vorlage „Rückstellung auflösen“).
- DATEV in Bilanz-Jahren: `datev._stapel_bilanz` (Eröffnung gegen 9000, Bestandskonten `BESTAND_KONTEN`, Erlöse ohne
  Automatik, USt 1776/3806, Vorsteuer 1576/1406, Skonto 8730/4730, Forderungsverlust 2400/6930, Gewerbesteuer 4320/7610).
- Die Buchungsliste und Kennzahlen bleiben nach Zahltag sortiert; eine im Dezember erfasste, im Januar bezahlte Rechnung
  erscheint dort im Januar („Rechnung vom …“), in der Bilanz im Dezember.

## 8. Grenzen

Kein E-Bilanz-Export (XBRL), kein ELSTER-Versand, keine Inventur/Warenbestände, keine Rücklagen § 6b/§ 7g, keine
latenten Steuern, kein Anhang. Rückstellungen, Rechnungsabgrenzungen und Kasse nur über Abschlussbuchungen. Gewinn-
ermittlung wechselt nur zum 1.1.; Rückwechsel Bilanz → EÜR nur mit Hinweis (Übergangsverlust rechnet Tab nicht).
