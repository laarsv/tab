# EÜR-Kategorien & Zeilen-Mapping — Tab

> **Zweck:** Single Source of Truth für die Zuordnung Buchungs-Kategorie → Zeile der amtlichen
> Anlage EÜR. Seed für das Tool `Tab`. Das Mapping ist **jahres-versioniert** — siehe §7.
>
> **Geltungsbereich:** Einzelunternehmer · **nur Kleinunternehmer (§19 UStG)** · kein
> Bankabruf, nur Belege · Multi-Gewerbe (eine EÜR pro Gewerbe).
>
> **Quelle der Zeilennummern:** Amtliche „Anleitung zur EÜR 2025" (ELSTER, Stand August 2025,
> Anlage EÜR Version 1.9.1.1). Veranlagungszeitraum (VZ) **2025**.
>
> **Legende Status:**
> - ✅ = Zeile amtlich aus der ELSTER-Anleitung 2025 verifiziert.
> - ⚠️ = Zeile beim finalen Abgleich gegen den Vordruck (Formular-PDF) bestätigen.
>   Betrifft nur laufende, **unbeschränkt abziehbare** Kosten — die Zuordnung ist
>   **gewinnneutral** (alle mindern den Gewinn identisch; nur die Formularzeile variiert).

---

## 1. Grundprinzipien (gelten im ganzen Tool)

1. **Kleinunternehmer = Brutto.** Jede Einnahme/Ausgabe wird mit dem Bruttobetrag gebucht.
   Keine USt-Aufschlüsselung, keine Vorsteuer.
2. **Folge daraus — diese Zeilen werden NIE befüllt:**
   - Zeile 15 **und** 17 (umsatzsteuerpflichtige Einnahmen + vereinnahmte USt)
   - Zeile 57 (gezahlte Vorsteuer)
   - Zeile 58 (an Finanzamt gezahlte USt)
   Das Tool blendet sie gar nicht erst ein.
   **Achtung:** Zeile **16** (umsatzsteuerfreie Einnahmen §4 UStG) wird sehr wohl
   genutzt — dort landet die Versicherungs-Courtage (§4 Nr. 11), siehe §3. Nie befüllt
   sind also nur **15, 17, 57, 58**.
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

| Kategorie | EÜR-Zeile 2025 | Besonderheit | Status |
|---|---|---|---|
| Einnahme Kleinunternehmer (z. B. App-/IAP-Erlöse) | **12** | Brutto, „vollständige Betriebseinnahmen" | ✅ |
| Umsatzsteuerfreie Einnahme §4 Nr. 11 (Versicherungs-Courtage) | **16** | nach §4 UStG steuerfrei | ✅ |
| Veräußerung/Entnahme Anlagevermögen (z. B. Hardware-Verkauf) | **19** | Erlös, bei KU brutto | ✅ |
| Private Kfz-Nutzung (1 %-Regelung, Betriebs-Kfz) | **20** | Nutzungsentnahme = Betriebseinnahme; Rechner im UI (1 % × Monate) | ⚠️ |
| *(berechnet)* Summe Betriebseinnahmen | **23** | Tool errechnet | ✅ |

**Hinweis Courtage (Z12 vs. Z16):** §4-Nr.11-Umsätze gehören sachlich in Zeile 16. Ob ein
reiner KU sie stattdessen in Zeile 12 sammelt, ist eine Steuerberater-Feinheit — **gewinnneutral**.
Default im Tool: **Zeile 16** für die Kategorie „Umsatzsteuerfreie Einnahme".

---

## 4. Ausgaben-Kategorien

### 4.1 Wareneinsatz / Fremdleistungen

| Kategorie | EÜR-Zeile 2025 | Besonderheit | Status |
|---|---|---|---|
| Bezogene Leistungen / Fremdleistungen / Provisionen (z. B. Tippgeber, freie Mitarbeiter) | **29** | — | ✅ |
| Waren/Roh-/Hilfsstoffe | **27** | für Makler/App selten | ✅ |

### 4.2 Abschreibungen (AfA) — eigene Buchungslogik, siehe §5

| Kategorie | EÜR-Zeile 2025 | Besonderheit | Status |
|---|---|---|---|
| AfA bewegliche Wirtschaftsgüter (MacBook, Hardware >800 €) | **33** | `ist_afa` | ✅ |
| GWG-Sofortabzug (≤800 € netto) | **36** | Vollabzug im Kaufjahr | ✅ |
| Restbuchwert ausgeschiedener Anlagegüter | **38** | bei Verkauf/Verschrottung | ✅ |

### 4.3 Raumkosten

| Kategorie | EÜR-Zeile 2025 | Besonderheit | Status |
|---|---|---|---|
| Miete betrieblich genutzte Räume / doppelte Haushaltsführung | **40** | — | ✅ |
| Sonstige Grundstücksaufwendungen (betrieblich) | **41** | — | ✅ |

### 4.4 Sonstige unbeschränkt abziehbare Betriebsausgaben (Zeilen 43–60)

| Kategorie | EÜR-Zeile 2025 | Besonderheit | Status |
|---|---|---|---|
| Telekommunikation (Telefon, Internet) | **43** | nur betrieblicher Anteil | ⚠️ |
| Miete/Leasing bewegliche WG (ohne Kfz) | 45–54 | — | ⚠️ |
| Versicherungen/Beiträge betrieblich (z. B. Vermögensschadenhaftpflicht) | 45–54 | für Makler wichtig | ⚠️ |
| Wartung/Reparatur/Instandhaltung | 45–54 | — | ⚠️ |
| Rechts-/Steuerberatung, Buchführung | 45–54 | — | ⚠️ |
| Fortbildung | 45–54 | — | ⚠️ |
| Werbung / Repräsentation | 45–54 | — | ⚠️ |
| Übernachtungs-/Reisenebenkosten (Geschäftsreise) | **44** | Verpflegung separat (Z64) | ✅ |
| Software/Hosting/SaaS (Hetzner, Brevo, Apple Developer 99 €, Domains) | **60** | „übrige unbeschränkt abziehbar" | ✅ |
| Bürobedarf / Porto / sonstige laufende Kosten | **60** | Catch-all | ✅ |

> **Zu den ⚠️-Zeilen (43–54):** Die exakte Formularzeile setze ich beim finalen Abgleich gegen
> den Vordruck 2025. Bis dahin sicherer Default: **Zeile 60** (übrige unbeschränkt abziehbare BA).
> Da alle hier unbeschränkt abziehbar sind, ist die Wahl 45–54 vs. 60 **gewinnneutral** —
> es ändert nur die Formularzeile, nicht die Steuerlast.

### 4.5 Beschränkt abziehbare Betriebsausgaben (Zeilen 62–67)

| Kategorie | EÜR-Zeile 2025 | Besonderheit | Status |
|---|---|---|---|
| Geschenke an Geschäftspartner | **62** | nur abziehbar wenn ≤50 €/Empfänger/Jahr; Empfänger am Beleg | ✅ |
| **Bewirtung (geschäftlich)** | **63** | **70 % abziehbar** (`abzug_quote=0.7`); Ort/Tag/Teilnehmer/Anlass pflichtig, ab 150 € Namen | ✅ |
| Verpflegungsmehraufwand (Reise) | **64** | nur Pauschbeträge (28 € / 14 €) | ✅ |
| Häusliches Arbeitszimmer | **65** | tatsächlich oder Jahrespauschale 1.260 € | ✅ |
| Homeoffice-Tagespauschale | **66** | 6 €/Tag, max. 1.260 €/Jahr | ✅ |

### 4.6 Kraftfahrzeug- & Fahrtkosten (Zeilen 68–73)

| Kategorie | EÜR-Zeile 2025 | Besonderheit | Status |
|---|---|---|---|
| Fahrtkosten privates Kfz (betrieblich) | **71** | 0,30 €/km **oder** tatsächliche Kosten | ✅ |
| Wege Wohnung↔Betriebsstätte (Entfernungspauschale) | **73** | 0,30 €/km (ab km 21: 0,38 €), Z72 = Kürzung | ✅ |
| Kfz-Kosten Betriebs-Kfz (Benzin, Versicherung, Reparatur, Leasing) | 68–70, vorläufig **60** | Gegenstück zur 1 %-Regelung (Z20) | ⚠️ |

> **Betriebs-Kfz mit 1 %-Regelung (integriert, bewusst schlank):** Laufende Kfz-Kosten als
> „Kfz-Kosten Betriebs-Kfz" buchen (⚠ vorläufig Zeile 60, final 68–70 — gewinnneutral), die
> private Nutzung monatlich/jährlich als Nutzungsentnahme über die Einnahme-Kategorie
> „Private Kfz-Nutzung (1 %-Regelung)" (Zeile 20). Der UI-Rechner nimmt 1 % vom auf volle
> 100 € **abgerundeten Bruttolistenpreis** je Monat. **Nicht abgedeckt** (Steuerberater/ELSTER):
> 0,03 %-Kürzung für Wege Wohnung–Betrieb (Z72), Kostendeckelung, Fahrtenbuch-Methode,
> USt auf die Wertabgabe. Vereinfachung: Die 1 %-Entnahme zählt im Tool **nicht** zur
> KU-Grenze (`ku_umsatz` bleibt nur `einnahme_ku`).

---

## 5. Sonderfälle, die das Datenmodell prägen

1. **AfA-Wirtschaftsgüter ≠ normale Ausgabe.** Eine AfA-Buchung speichert Anschaffungskosten,
   Datum und Nutzungsdauer; in die EÜR fließt der **Jahres-AfA-Betrag** (Zeile 33), nicht der
   Kaufpreis. **Computer-Hardware/Software:** Nutzungsdauer 1 Jahr zulässig → faktisch
   Vollabzug im Kaufjahr, läuft aber als AfA über Zeile 33 (nicht als laufende Ausgabe).
2. **GWG ≤800 € netto** → Sofortabzug Zeile 36 (kein AfA-Plan nötig).
3. **Bewirtung:** Tool speichert 100 % des Belegs, EÜR-Export rechnet **70 %** in Zeile 63.
   Die 30 % nicht abziehbar nicht doppelt erfassen.
4. **Geschenke:** ≤50 €/Empfänger/Jahr abziehbar (Zeile 62), Empfängername am Beleg.

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

Die Zeilennummern der Anlage EÜR **verschieben sich jährlich** (Beispiel 2024→2025: Zeile 12
präzisiert, neue Zeilen eingefügt). Daher:

- Das Mapping liegt als **Tabelle pro VZ** vor (`euer_mapping[jahr]`), nicht hartcodiert.
- Eine Buchung speichert die Kategorie (stabil), **nicht** die Zeilennummer. Die Zeile wird
  beim Export aus der Mapping-Version des jeweiligen Jahres aufgelöst.
- Jährlich vor Steuersaison: neue ELSTER-Anleitung ziehen, Mapping-Version anlegen, Diff prüfen.

**Aktuelle Version:** VZ 2025 (ELSTER-Anleitung Stand 08/2025). Die ⚠️-Zeilen (43–54) sind vor
Scharfstellung gegen den Vordruck 2025 final zu bestätigen.

---

*Quelle: ELSTER „Anleitung zur EÜR 2025". Dieses Dokument ist eine technische Spezifikation,
keine Steuerberatung.*
