# EÜR-Kategorien & Zeilen-Mapping — Tab

> **Zweck:** Single Source of Truth für die Zuordnung Buchungs-Kategorie → Zeile der amtlichen
> Anlage EÜR. Seed für das Tool `Tab` (`backend/app/seed.py`). Das Mapping ist
> **jahres-versioniert** — siehe §7.
>
> **Geltungsbereich:** Einzelunternehmer · **nur Kleinunternehmer (§19 UStG)** · kein
> Bankabruf, nur Belege · Multi-Gewerbe (eine EÜR pro Gewerbe).
>
> **Quellen der Zeilennummern:** Amtliche Vordrucke der Anlage EÜR, jeweils Seiten 3–5 des
> BMF-Schreibens — **VZ 2025:** BMF vom 29.08.2025 (Vordruck 2025AnlEÜR801–803),
> **VZ 2026:** BMF vom 01.09.2026 (Vordruck 2026AnlEÜR801–803, Anleitung Stand 08/2026).
>
> **Legende Status:**
> - ✅ = Zeile am amtlichen Vordruck verifiziert.
> - ⚠️ = 2025: laufende, **unbeschränkt abziehbare** Kosten stehen bewusst auf dem
>   gewinnneutralen Default **Zeile 60** („Übrige"); die Vordruck-Zeile ist daneben genannt.
>   Alle mindern den Gewinn identisch, nur die Formularzeile variiert. **2026 ist alles final.**

---

## 1. Grundprinzipien (gelten im ganzen Tool)

1. **Kleinunternehmer = Brutto.** Jede Einnahme/Ausgabe wird mit dem Bruttobetrag gebucht.
   Keine USt-Aufschlüsselung, keine Vorsteuer.
2. **Folge daraus — diese Zeilen werden NIE befüllt:**
   - Zeile 15 **und** 17 (umsatzsteuerpflichtige Einnahmen + vereinnahmte USt)
   - Vorsteuer und an das Finanzamt gezahlte USt: **2025: Zeilen 57 + 58, 2026: Zeilen 58 + 59**
   Das Tool blendet sie gar nicht erst ein.
   **Achtung:** Zeile **16** (umsatzsteuerfreie Einnahmen §4 UStG) wird sehr wohl
   genutzt — dort landet die Versicherungs-Courtage (§4 Nr. 11), siehe §3. Und 2026 ist
   Zeile 57 „Übrige Schuldzinsen" — die ist normal befüllbar.
3. **Zufluss-/Abfluss-Prinzip (§11 EStG):** Buchungsdatum = **Zahlungsdatum**, nicht
   Rechnungsdatum. (Eine Ausnahme: regelmäßig wiederkehrende Zahlungen ±10 Tage um den
   Jahreswechsel — Edge-Case, nicht in Phase 1.)
4. **Eine EÜR pro Gewerbe.** Jedes Gewerbe (z. B. Makler, App) erzeugt eine eigene Anlage EÜR.
   Das Mapping ist pro Gewerbe identisch; getrennt wird nur die Datenmenge.
5. **KU-Grenz-Guard:** Überschreitet der Gesamtumsatz eines Gewerbes 25.000 € (Vorjahr)
   bzw. 100.000 € (laufend), ist der KU-Status weg. Das Tool deckt das **nicht** ab →
   Warnhinweis ausgeben, Verweis auf Steuerberater. **Wichtig (§19 Abs. 2 UStG):** Beim
   Gesamtumsatz bleiben steuerfreie Umsätze nach §4 Nr. 11 (Courtage!) und Umsätze von
   Wirtschaftsgütern des Anlagevermögens **außer Ansatz** — der Guard vergleicht daher nur
   die Kategorie „Einnahme Kleinunternehmer" (`einnahme_ku`) gegen die Grenzen.

---

## 2. Datenmodell — Kategorie-Felder

Jede Kategorie trägt:

| Feld | Werte | Zweck |
|---|---|---|
| `typ` | `einnahme` / `ausgabe` | Grundrichtung |
| `euer_zeile` | Integer (pro VZ, s. §7) | Ziel-Zeile im Formular |
| `abzug_quote` | `1.0` / `0.7` / … | z. B. Bewirtung 0,7 (Tool speichert 100 %, EÜR bekommt 70 %) |
| `ist_afa` | bool | AfA-Wirtschaftsgut → eigene Buchungslogik (Nutzungsdauer/Jahres-AfA) |
| `belegpflicht_extra` | bool | z. B. Bewirtung (Ort/Anlass/Teilnehmer), Geschenke (Empfänger) |

---

## 3. Einnahmen-Kategorien

| Kategorie | Zeile 2025 | Zeile 2026 | Besonderheit | Status |
|---|---|---|---|---|
| Einnahme Kleinunternehmer (z. B. App-/IAP-Erlöse) | **12** | **12** | Brutto, „vollständige Betriebseinnahmen" | ✅ |
| Umsatzsteuerfreie Einnahme §4 Nr. 11 (Versicherungs-Courtage) | **16** | **16** | nach §4 UStG steuerfrei | ✅ |
| Veräußerung/Entnahme Anlagevermögen (z. B. Hardware-Verkauf) | **19** | **19** | Erlös, bei KU brutto | ✅ |
| Private Kfz-Nutzung (1 %-Regelung, Betriebs-Kfz) | **20** | **20** | Nutzungsentnahme = Betriebseinnahme; Rechner im UI (1 % × Monate) | ✅ |
| Sonstige Entnahmen (Sach-/Nutzungs-/Leistungsentnahme) | **21** | **21** | „Sonstige Sach-, Nutzungs- und Leistungsentnahmen" | ✅ |
| *(berechnet)* Summe Betriebseinnahmen | **23** | **23** | Tool errechnet | ✅ |

**Hinweis Courtage (Z12 vs. Z16):** §4-Nr.11-Umsätze gehören sachlich in Zeile 16. Ob ein
reiner KU sie stattdessen in Zeile 12 sammelt, ist eine Steuerberater-Feinheit — **gewinnneutral**.
Default im Tool: **Zeile 16** für die Kategorie „Umsatzsteuerfreie Einnahme".

---

## 4. Ausgaben-Kategorien

> **2026-Besonderheit:** Der Vordruck bekommt eine neue **Zeile 27** (Rücklage Tierbewertung,
> nur Land-/Forstwirte). Dadurch folgt auf den Übertrag Z28 die Zeile **Waren erst auf Z29**
> (2025: Z27), alles danach rückt meist um 1 nach hinten.

### 4.1 Wareneinsatz / Fremdleistungen / Personal

| Kategorie | Zeile 2025 | Zeile 2026 | Besonderheit | Status |
|---|---|---|---|---|
| Waren/Roh-/Hilfsstoffe | **27** | **29** | für Makler/App selten | ✅ |
| Bezogene Leistungen / Fremdleistungen / Provisionen (z. B. Tippgeber, freie Mitarbeiter) | **29** | **30** | — | ✅ |
| Personal: Löhne, Gehälter, Minijob-Pauschalabgaben | 60 (⚠ Vordruck: 30) | **31** | Minijob: Lohn + Abgaben an Minijob-Zentrale | ✅ (2026) |

### 4.2 Abschreibungen (AfA) — eigene Buchungslogik, siehe §5

| Kategorie | Zeile 2025 | Zeile 2026 | Besonderheit | Status |
|---|---|---|---|---|
| AfA bewegliche Wirtschaftsgüter (MacBook, Hardware >800 €) | **33** | **34** | `ist_afa` | ✅ |
| GWG-Sofortabzug (≤800 € netto) | **36** | **37** | Vollabzug im Kaufjahr | ✅ |
| Restbuchwert ausgeschiedener Anlagegüter | **38** | **39** | bei Verkauf/Verschrottung | ✅ |

### 4.3 Raumkosten

| Kategorie | Zeile 2025 | Zeile 2026 | Besonderheit | Status |
|---|---|---|---|---|
| Miete betrieblich genutzte Räume | **39** | **40** | „Miete/Pacht für Geschäftsräume und betrieblich genutzte Grundstücke" | ✅ |
| Sonstige Grundstücksaufwendungen (betrieblich) | **41** | **42** | ohne Schuldzinsen und AfA | ✅ |

Die Aufwendungen für **doppelte Haushaltsführung** haben eine eigene Zeile (2025: 40, 2026: 41) —
keine eigene Kategorie, bei Bedarf als „Sonstige" erfassen und mit dem Steuerberater klären.

### 4.4 Sonstige unbeschränkt abziehbare Betriebsausgaben

| Kategorie | Zeile 2025 | Zeile 2026 | Besonderheit | Status |
|---|---|---|---|---|
| Telekommunikation (Telefon, Internet) | 60 (⚠ Vordruck: 43) | **44** | nur betrieblicher Anteil | ✅ (2026) |
| Übernachtungs-/Reisenebenkosten (Geschäftsreise) | **44** | **45** | Verpflegung separat | ✅ |
| Fortbildung | 60 (⚠ Vordruck: 45) | **46** | ohne Reisekosten | ✅ (2026) |
| Rechts-/Steuerberatung, Buchführung | 60 (⚠ Vordruck: 46) | **47** | — | ✅ (2026) |
| Miete/Leasing bewegliche WG (ohne Kfz) | 60 (⚠ Vordruck: 47) | **48** | — | ✅ (2026) |
| Wartung/Reparatur/Instandhaltung | 60 (⚠ Vordruck: 48) | **49** | „Erhaltungsaufwendungen", ohne Gebäude und Kfz | ✅ (2026) |
| Versicherungen/Beiträge betrieblich (z. B. Vermögensschadenhaftpflicht) | 60 (⚠ Vordruck: 49) | **50** | „Beiträge, Gebühren, Abgaben und Versicherungen"; für Makler wichtig | ✅ (2026) |
| Gebühren & Abgaben (Behörden, Gewerbeanmeldung) | 60 (⚠ Vordruck: 49) | **50** | gleiche Zeile wie Versicherungen; **nicht** Bußgelder/Verwarnungsgelder (nicht abziehbar; „Sonstige beschränkt abziehbare Betriebsausgaben“, 2025: Z67, 2026: Z68) | ✅ (2026) |
| Werbung / Repräsentation | 60 (⚠ Vordruck: 54) | **55** | „Werbekosten" | ✅ (2026) |
| Software/Hosting/SaaS (Hetzner, Brevo, Apple Developer 99 €, Domains) | **60** | **61** | „übrige unbeschränkt abziehbar" (Alternative: „Laufende EDV-Kosten" Z50/Z51) | ✅ |
| Bürobedarf / Porto / sonstige laufende Kosten | **60** | **61** | Catch-all (Alternative für reinen Bürobedarf: „Arbeitsmittel" Z51/Z52) | ✅ |
| Kontoführung & Zahlungsgebühren (Bank, PayPal, Stripe) | **60** | **61** | häufigster Kleinposten | ✅ |

> **Zu 2025/⚠:** Bei den ⚠-Zeilen stehen 2025 bewusst weiter Zeile 60. Da alle unbeschränkt
> abziehbar sind, ist die Wahl „Fachzeile" vs. 60 **gewinnneutral** — es ändert nur die
> Formularzeile, nicht die Steuerlast. 2026 sind die Fachzeilen gesetzt.

### 4.5 Beschränkt abziehbare Betriebsausgaben

| Kategorie | Zeile 2025 | Zeile 2026 | Besonderheit | Status |
|---|---|---|---|---|
| Geschenke an Geschäftspartner | **62** | **63** | nur abziehbar wenn ≤50 €/Empfänger/Jahr; Empfänger am Beleg | ✅ |
| **Bewirtung (geschäftlich)** | **63** | **64** | **70 % abziehbar** (`abzug_quote=0.7`); Ort/Tag/Teilnehmer/Anlass pflichtig, ab 150 € Namen | ✅ |
| Verpflegungsmehraufwand (Reise) | **64** | **65** | nur Pauschbeträge (28 € / 14 €) | ✅ |
| Häusliches Arbeitszimmer | **65** | **66** | tatsächlich oder Jahrespauschale 1.260 € | ✅ |
| Homeoffice-Tagespauschale | **66** | **67** | 6 €/Tag, max. 1.260 €/Jahr | ✅ |

### 4.6 Kraftfahrzeug- & Fahrtkosten

| Kategorie | Zeile 2025 | Zeile 2026 | Besonderheit | Status |
|---|---|---|---|---|
| Fahrtkosten privates Kfz (betrieblich) | **71** | **72** | „Nutzungseinlage"; 0,30 €/km **oder** tatsächliche Kosten | ✅ |
| Wege Wohnung↔Betriebsstätte (Entfernungspauschale) | **73** | **74** | **bis 2025** 0,30 €/km (ab km 21: 0,38 €), **ab 2026 0,38 €/km vom 1. km an**; Kürzungszeile (Z72 / Z73) nicht abgedeckt | ✅ |
| Kfz-Kosten Betriebs-Kfz (Benzin, Versicherung, Reparatur, Leasing) | 60 (⚠ Vordruck: 68–70) | **71** | Gegenstück zur 1 %-Regelung (Z20). Vordruck 2026: Leasing **Z69**, Steuern/Versicherung/Maut **Z70**, Sonstige tatsächliche (Treibstoff, Reparatur) **Z71** — Tab bucht alles auf Z71 | ✅ (2026, vereinfacht) |
| ÖPNV / Bahn / Taxi (Geschäftsfahrten) | 60 (⚠ Vordruck: 70) | **71** | „Sonstige tatsächliche Fahrtkosten … öffentliche Verkehrsmittel"; Deutschlandticket nur anteilig; Wege Wohnung↔Betrieb bleiben bei Z74 | ✅ (2026) |
| Zinsen & Finanzierungskosten (betrieblich) | 60 (⚠ Vordruck: 55/56) | **57** | „Übrige Schuldzinsen" (bis 2.050 € unbeschränkt abziehbar, darüber Anlage SZ); Zinsen für Anlagen-Darlehen wären Z56 — nicht getrennt; §-4-Abs.-4a-Prüfung = Steuerberater | ✅ (2026, vereinfacht) |

> **Betriebs-Kfz mit 1 %-Regelung (integriert, bewusst schlank):** Laufende Kfz-Kosten als
> „Kfz-Kosten Betriebs-Kfz" buchen (2026: Zeile 71), die
> private Nutzung monatlich/jährlich als Nutzungsentnahme über die Einnahme-Kategorie
> „Private Kfz-Nutzung (1 %-Regelung)" (Zeile 20). Der UI-Rechner nimmt je Monat 1 % der
> **Bemessungsgrundlage** = Bruttolistenpreis × Antriebs-Satz (Verbrenner 1,0 · Plug-in-Hybrid
> 0,5 · E-Auto 0,25), auf volle 100 € abgerundet. Grenzen (weicher Hinweis, keine harte
> Prüfung): 0,25 % nur bis 70.000 € Listenpreis (Anschaffung ab 07/2025: 100.000 €), Hybrid
> nur mit Mindest-E-Reichweite. **Nicht abgedeckt** (Steuerberater/ELSTER):
> 0,03 %-Kürzung für Wege Wohnung–Betrieb (2025: Z72, 2026: Z73), Kostendeckelung,
> Fahrtenbuch-Methode, USt auf die Wertabgabe. Vereinfachung: Die 1 %-Entnahme zählt im Tool
> **nicht** zur KU-Grenze (`ku_umsatz` bleibt nur `einnahme_ku`).

---

## 5. Sonderfälle, die das Datenmodell prägen

1. **AfA-Wirtschaftsgüter ≠ normale Ausgabe.** Eine AfA-Buchung speichert Anschaffungskosten,
   Datum und Nutzungsdauer; in die EÜR fließt der **Jahres-AfA-Betrag** (2025: Zeile 33,
   2026: Zeile 34), nicht der Kaufpreis. **Computer-Hardware/Software:** Nutzungsdauer 1 Jahr
   zulässig → faktisch Vollabzug im Kaufjahr, läuft aber als AfA über die AfA-Zeile (nicht als
   laufende Ausgabe).
2. **GWG ≤800 € netto** → Sofortabzug (2025: Zeile 36, 2026: Zeile 37), kein AfA-Plan nötig.
3. **Bewirtung:** Tool speichert 100 % des Belegs, EÜR-Export rechnet **70 %** in die
   Bewirtungszeile (2025: 63, 2026: 64). Die 30 % nicht abziehbar nicht doppelt erfassen.
4. **Geschenke:** ≤50 €/Empfänger/Jahr abziehbar, Empfängername am Beleg.

---

## 6. Export-Logik

Der Export ist **kein** ELSTER-Direktversand. Er liefert zwei Artefakte pro Gewerbe + Jahr:

1. **EÜR-Summenblatt:** je befüllte Zeile eine Summe (`Zeile-Nr | Bezeichnung | Betrag`) —
   genau die Zahlen, die ins Steuerprogramm/ELSTER übertragen werden.
2. **Beleg-Journal (CSV):** alle Einzelbuchungen (Datum, Betrag, Kategorie, Zeile,
   Beschreibung) als Nachweis/Backup.

Beträge `tabular-nums`, Bewirtung im Summenblatt bereits mit 70 % gerechnet.

---

## 7. Versionierung (wichtig!)

Die Zeilennummern der Anlage EÜR **verschieben sich jährlich** (2024→2025: Zeile 12
präzisiert, neue Zeilen eingefügt; 2025→2026: neue Zeile 27 → alles ab Waren rückt nach hinten).
Daher:

- Das Mapping liegt als **Tabelle pro VZ** vor (`euer_mapping[jahr]`, in `seed.py` je Jahr als
  `ZEILEN_<jahr>`/`MAPPING_<jahr>`), nicht hartcodiert — **nie ein Jahr aus dem anderen ableiten,
  immer am Vordruck prüfen.**
- Eine Buchung speichert die Kategorie (stabil), **nicht** die Zeilennummer. Die Zeile wird
  beim Export aus der Mapping-Version des jeweiligen Jahres aufgelöst.
- Jährlich ab Herbst: BMF-Schreiben „Anlage EÜR <Jahr>" ziehen (Vordruck-Seiten 3–5 **als Bild
  ansehen**, die Textebene vermischt die Spalten), Mapping-Version anlegen, Diff prüfen, auch die
  Anleitung auf geänderte Sätze lesen (z. B. Entfernungspauschale ab 2026).

**Aktuelle Versionen:** VZ 2025 (BMF 29.08.2025) und VZ 2026 (BMF 01.09.2026), beide verifiziert.

---

*Quelle: BMF-Schreiben „Anlage EÜR" 2025 und 2026 (Vordrucke + Anleitung). Dieses Dokument ist
eine technische Spezifikation, keine Steuerberatung.*
