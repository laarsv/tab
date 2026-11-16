# Verfahrensdokumentation Buchführung mit Tab

Verfahrensdokumentation nach den GoBD (BMF-Schreiben vom 28.11.2019, Rz. 151 ff.) für die Gewinnermittlung mit
Tab. Aufbau nach dem Muster der AWV (Allgemeine Beschreibung, Anwender-, technische System- und
Betriebsdokumentation, internes Kontrollsystem).

**Stand:** 15.11.2026 · **Version:** 2 · **Verantwortlich:** der Inhaber (siehe 1.1)

**Das ist die Vorlage.** Das Repo ist öffentlich: Die ausgefüllte Fassung (Abschnitte mit **[ausfüllen]**)
wird als Kopie außerhalb des Repos geführt und mit dem Jahresarchiv aufbewahrt, nie hier eingecheckt. Ändert sich ein Ablauf, wird diese Datei angepasst
und die Änderung in Abschnitt 9 eingetragen; frühere Fassungen bleiben über die Git-Historie des Repos und als
Ausdruck je Jahr erhalten (siehe 7).

---

## 1. Allgemeine Beschreibung

### 1.1 Unternehmen

| | |
|---|---|
| Inhaber | **[ausfüllen]**, Einzelunternehmer |
| Anschrift | **[ausfüllen]** |
| Steuernummer | **[ausfüllen]** |
| Tätigkeit | **[ausfüllen, z. B. Versicherungsvermittlung (steuerfrei nach § 4 Nr. 11 UStG) und IT-Dienstleistungen]** |
| Gewinnermittlung | Einnahmen-Überschuss-Rechnung (§ 4 Abs. 3 EStG), Anlage EÜR |
| Umsatzsteuer | Kleinunternehmer (§ 19 UStG); steuerfreie Umsätze nach § 4 Nr. 11 zählen nicht zur Grenze (§ 19 Abs. 2 UStG) |
| Beschäftigte | **[ausfüllen: Anzahl, Art (z. B. Minijob); wer die Lohnabrechnung macht]** — die Buchführung in Tab erledigt der Inhaber selbst |
| Steuerberatung | **[ausfüllen: Kanzlei, ob sie Zugang zu Tab hat]** |

**[ausfüllen, falls vorher ein anderes Programm genutzt wurde: welches, für welche Jahre, bis wann.]**
Altdaten siehe 7.3.

### 1.2 Eingesetzte Software

| Zweck | System |
|---|---|
| Belege, Buchungen, EÜR, Rechnungen, Mahnungen, Angebote, Anlagen (AfA), Bankabgleich | **Tab** (eigene Webanwendung, `https://tab.vrwb.de`) |
| Geschäftskonto | **[ausfüllen: Bank, z. B. Vivid Business]**; Kontoauszüge als Datei bzw. Abruf nach Tab |
| E-Mail für Belege und Rechnungsversand | Google Mail (IMAP/SMTP mit App-Passwort) |
| Übermittlung an das Finanzamt | ELSTER (manuelle Eingabe der Werte aus dem Summenblatt) |

Tab wird vom Inhaber selbst entwickelt und betrieben. Es ist **nicht zertifiziert** (kein Testat nach
IDW PS 880). Diese Dokumentation beschreibt, wie Ordnungsmäßigkeit trotzdem sichergestellt wird.

---

## 2. Belege: Eingang, Erfassung, Ablage

### 2.1 Wege, auf denen Belege nach Tab kommen

1. **Digitale Belege per E-Mail** (Rechnungen von Lieferanten, Plattformen): Der Inhaber leitet sie an seine
   `+tab`-Adresse weiter oder lässt sie dorthin schicken. Tab holt diese Mails alle 10 Minuten ab (nur
   Absender aus dem Vertrauenskreis, Postfach wird nicht verändert) und legt die Anhänge im
   **Beleg-Eingang** ab.
2. **Hochladen** im Browser (PDF, JPG, PNG, XML) in den Beleg-Eingang.
3. **Teilen vom Handy** (installierte App, Android) in den Beleg-Eingang.
4. **Papierbelege**: werden fotografiert oder gescannt und über Weg 2 oder 3 hochgeladen
   (ersetzendes Scannen, siehe 2.4).
5. **E-Rechnungen** (XRechnung, ZUGFeRD): werden wie andere Dateien empfangen; Tab liest die strukturierten
   Daten aus. Die XML-Datei bzw. das PDF mit eingebetteter XML ist das Original und wird unverändert gespeichert.

Tab nimmt nur PDF, JPG, PNG und XML an, mit Größenbegrenzung. Jede Datei wird unverändert unter einem
zufälligen Namen gespeichert, der ursprüngliche Dateiname wird mitgeführt.

### 2.2 Erfassung (Buchen)

- Belege im Eingang werden über das Buchungsfenster verbucht: Datum, Beschreibung, eine oder mehrere
  Positionen mit **Kategorie** und **Betrag (brutto)**, ggf. Privatanteil. Tab schlägt Betrag, Datum,
  Lieferant und Kategorie aus dem Beleg vor; der Inhaber **prüft und bestätigt** jeden Vorschlag.
- Die Kategorie bestimmt die Zeile der Anlage EÜR; die Zuordnung ist je Jahr hinterlegt und wird erst beim
  Export aufgelöst.
- Gebucht wird nach dem **Zufluss-/Abflussprinzip** (§ 11 EStG) mit dem Datum der Zahlung bzw. des Belegs.
- **Zeitnähe:** Belege werden spätestens bis zum Ende des Folgemonats erfasst, Bankumsätze nach jedem
  Kontoauszug bzw. Abruf. **[anpassen, falls anders gehandhabt]**
- Ausgangsrechnungen entstehen in Tab (fortlaufende Nummer je Jahr, keine Lücken; Löschen nur der letzten
  Nummer vor Versand). Zahlungseingänge werden als Einnahme gebucht und mit der Rechnung verknüpft.
- Abschreibungen werden als Anlage erfasst; Tab berechnet die jährliche AfA, sie wird nicht gebucht.

### 2.3 Verknüpfung Beleg – Buchung – Bankumsatz

Jede Buchung trägt ihre Belegdateien; jeder Bankumsatz wird genau einer Buchung zugeordnet oder mit Grund
als „ignoriert“ markiert (z. B. privat, Umbuchung). So ist jeder Geldfluss auf dem Geschäftskonto entweder
belegt oder begründet.

**Bankumsätze kommen** als Datei (Kontoauszug CAMT.053, CSV oder PDF) oder per **Bankabruf**: Der Inhaber verbindet das
Konto einmalig über den Kontoinformationsdienst Enable Banking (PSD2, nur lesender Zugriff, Freigabe bei der Bank, gültig
höchstens 180 Tage); Tab holt danach gebuchte Umsätze bis zu viermal am Tag. Derselbe Umsatz wird nur einmal übernommen,
auch wenn er per Datei und per Abruf kommt. Jeder Abruf ist als Import protokolliert.

**Automatische Zuordnung:** Eindeutige Fälle ordnet Tab selbst zu (nach jedem Import und stündlich): Zahlungseingang
= offener Betrag genau einer Rechnung; Abbuchung = fälliger Termin eines Dauerbelegs (Betrag, Bezeichnung, Termin);
Umsatz = bereits vorhandene Buchung; Abbuchung = genau ein Beleg im Eingang mit gleichem Betrag und passendem Datum,
wenn die Kategorie aus früheren Buchungen derselben Gegenpartei eindeutig ist. **Ohne Beleg bucht Tab nicht.** Jede
automatische Zuordnung ist am Umsatz mit Begründung gekennzeichnet, steht im Änderungsprotokoll und kann
zurückgenommen werden. Der Inhaber sieht die automatisch gebuchten Umsätze beim monatlichen Bankabgleich durch.

### 2.4 Ersetzendes Scannen von Papierbelegen

Papierbelege werden digitalisiert und danach nicht mehr in Papier aufbewahrt (GoBD Rz. 136 ff.).

1. Der Inhaber digitalisiert den Beleg selbst, zeitnah nach Erhalt (Smartphone-Kamera oder Scanner),
   vollständig (alle Seiten, Vorder- und Rückseite, wenn beschrieben) und farbig.
2. Er prüft am Bildschirm, dass Betrag, Datum, Aussteller und Leistung **lesbar** sind; ist das nicht der
   Fall, wird neu digitalisiert.
3. Die Datei wird in Tab hochgeladen und bis zum Ende des Folgemonats verbucht.
4. Nach dem Verbuchen darf das Papier vernichtet werden. **Ausnahmen, die im Original aufbewahrt werden:**
   Belege, bei denen das Gesetz das Original verlangt oder deren Beweiswert am Papier hängt (z. B.
   Zollbelege, notarielle Urkunden, Belege mit Siegel, Wertpapiere). **[ausfüllen: eigene Ausnahmen]**
5. Eine nachträgliche Bearbeitung der Bilddatei (Zuschneiden, Retusche) findet nicht statt.

---

## 3. Technische Systemdokumentation

- **Aufbau:** Webanwendung (FastAPI/Python, React), eine SQLite-Datenbank, Belegdateien im Dateisystem.
  Betrieb in Docker-Containern auf einem gemieteten Server bei Hetzner (Rechenzentrum in Deutschland).
- **Datenhaltung:** Beträge als ganze Cent; Buchungen speichern Kategorie, nie die EÜR-Zeile.
  Schemaänderungen über nummerierte Migrationen, die nur ergänzen.
- **Unveränderbarkeit (GoBD Rz. 58 ff.):**
  - **Änderungsprotokoll:** Datenbank-Trigger schreiben jede Anlage, Änderung und Löschung von Gewerbe,
    Buchungen, Positionen, Belegen, Anlagen, Fahrten, Rechnungen, Mahnungen, Bank- und Angebotsdaten mit
    altem und neuem Stand, Zeitpunkt und handelnder Person ins Protokoll.
  - **Hash-Kette:** Jeder Protokolleintrag enthält den SHA-256 des vorigen; das Protokoll kann nur ergänzt
    werden. „Alles prüfen“ rechnet die Kette nach.
  - **Jahresabschluss (Festschreibung):** Nach Jahresende schließt der Inhaber das Jahr ab. Danach sperren
    Trigger jede Änderung an Buchungen, Positionen, den daran hängenden Belegen, Fahrten und
    AfA-relevanten Anlagedaten dieses Jahres. Beim Abschluss entsteht ein **Siegel** (SHA-256 über alle
    gesperrten Daten einschließlich des SHA-256 jeder Belegdatei).
  - Wiederöffnen eines Jahres ist nur mit Begründung möglich; Begründung und neues Siegel stehen im Protokoll.
  - **Grenze:** Wer direkten Zugriff auf den Server hat, könnte Trigger entfernen. Kette und Siegel machen
    eine solche Änderung sichtbar, verhindern sie aber nicht. Den Prüfwert jedes Jahres (Kopf der Kette und
    Siegel) bewahrt der Inhaber deshalb **außerhalb des Servers** auf (siehe 7.1).
- **Vor Einführung des Protokolls** (Schemastand 20, ausgeliefert am 08.11.2026) erfasste Daten sind
  nicht protokolliert; das Protokoll beginnt mit einem Startwert.

---

## 4. Betriebsdokumentation

### 4.1 Zugriff

- Anmeldung nur mit Google-Konto, E-Mail und Passwort oder Passkey; Sitzung als geschütztes Cookie.
- Jedes Gewerbe gehört genau einem Konto; Zugriff auf fremde Daten ist technisch ausgeschlossen.
- **Steuerberatung:** auf Einladung ein eigenes Konto, **nur lesend**.
- **KI-Assistenten:** nur über ein widerrufbares Zugangs-Token bzw. eine OAuth-Freigabe, **nur lesend**;
  Änderungen nur als Vorschlag, den der Inhaber übernimmt oder verwirft.
- Der Server ist nur per SSH-Schlüssel des Inhabers erreichbar.

### 4.2 Datensicherung

| Was | Wann | Wohin | Aufbewahrung |
|---|---|---|---|
| Datenbank (konsistenter Snapshot) | täglich 03:15 | Backup-Laufwerk des Servers | ca. 7 Tage |
| Belegdateien | täglich 03:15 (Spiegel) | Backup-Laufwerk des Servers | Spiegel löscht nicht |
| Einstellungsdatei mit Schlüsseln | täglich 03:15 | Backup-Laufwerk des Servers | ca. 7 Tage |
| Alles oben | täglich 03:35 | NAS des Inhabers (anderer Standort) | 14 täglich, 8 wöchentlich, 12 monatlich |
| Jahresarchiv (siehe 7.1) | nach jedem Jahresabschluss | lokal beim Inhaber, zusätzlich **[ausfüllen]** | 10 Jahre |

Der Status jeder Nacht wird automatisch geprüft; bei Ausfall kommt eine Warnung.
**Wiederherstellungsprobe:** am 15.11.2026 die Sicherung der Nacht entpackt — Datenbank unversehrt
(`integrity_check ok`, Schemastand 32), Datenmengen gleich dem Stand der Nacht, alle Belegdateien im
Spiegel. Die Probe wird mindestens jährlich nach dem Jahresabschluss wiederholt.

### 4.3 Änderungen an Tab

Tab wird über Git versioniert; jede Änderung ist ein Commit mit Beschreibung. Vor dem Ausliefern laufen
Tests und der Build. Änderungen an der fachlichen Logik (EÜR-Zuordnung, AfA, Rechnungen) werden in der
Projektdokumentation festgehalten. Jedes Jahr wird die Zuordnung zur neuen Anlage EÜR gegen den amtlichen
Vordruck geprüft, bevor das Jahr bebucht wird.

---

## 5. Internes Kontrollsystem

| Kontrolle | Wie | Wann |
|---|---|---|
| Bankabgleich | Jeder Umsatz des Geschäftskontos ist zugeordnet oder begründet ignoriert; Tab prüft Anfangs- gegen Endsaldo des Auszugs | nach jedem Auszug bzw. Abruf |
| Doppelte Umsätze | Tab erkennt bereits importierte Umsätze am Fingerabdruck | automatisch |
| Beleg-Eingang leer | Kein Beleg bleibt unverbucht; Tab zeigt offene und fällige Belege an | monatlich |
| Offene Rechnungen | Überfällige Rechnungen erscheinen auf der Übersicht, Mahnwesen | laufend |
| Kleinunternehmergrenze | Tab warnt, wenn der maßgebliche Umsatz die Grenzen erreicht | laufend |
| Jahres-Check | Themenliste (Auto, Homeoffice, Bewirtung …) vor dem Abschluss | jährlich |
| Abschluss und Siegel | „Alles prüfen“ (Kette, Siegel, Trigger) vor und nach dem Abschluss | jährlich |
| Summenblatt gegen Erklärung | Werte in ELSTER = Summenblatt des abgeschlossenen Jahres | jährlich |

---

## 6. Steuererklärung

Nach Abschluss des Jahres erzeugt Tab das EÜR-Summenblatt je Zeile der Anlage EÜR. Der Inhaber überträgt die
Werte in ELSTER und reicht die Erklärung ein; Tab übermittelt nichts. Fristen stehen in Tab unter „Fristen“.

---

## 7. Aufbewahrung

### 7.1 Jahresarchiv

Nach dem Abschluss lädt der Inhaber das **Jahresarchiv** (ZIP) herunter: Summenblatt, Beleg-Journal,
Fahrten, alle Belegdateien des Jahres, Änderungsprotokoll, Prüfwert und eine Prüfsummendatei
(`sha256sum -c pruefsummen.sha256`). Er bewahrt es zusammen mit einem Ausdruck bzw. einer PDF dieser
Verfahrensdokumentation in der gültigen Fassung außerhalb des Servers auf.

### 7.2 Fristen

Buchungen, Belege, Jahresabschlüsse: **8 Jahre** für Buchungsbelege, **10 Jahre** für Bücher,
Aufzeichnungen und Jahresabschlüsse (§ 147 AO, § 14b UStG; Stand 2026 — bei Änderungen der Fristen
anpassen). Die Frist beginnt mit dem Ende des Kalenderjahres der letzten Eintragung bzw. des Belegs.
Während der Frist bleibt Tab bzw. das Jahresarchiv maschinell auswertbar (Datenzugriff der
Finanzverwaltung, § 147 Abs. 6 AO: CSV-Dateien im Archiv, Lesezugang für Prüfer bei Bedarf).

### 7.3 Altdaten aus einem früheren Programm

Die im früheren Programm geführten Jahre **[ausfüllen]** werden vor Ende des Vertrags vollständig
exportiert (Belege, Buchungen, Rechnungen, Auswertungen, DATEV-/CSV-Export) und wie 7.1 aufbewahrt.
**[ausfüllen: Exportdatum, Ablageort]**

---

## 8. Mitgeltende Unterlagen

- `CLAUDE.md` im Repo: fachliche Regeln und technische Details von Tab
- `EUER_KATEGORIEN.md`: Kategorien und Zuordnung zur Anlage EÜR
- Backup-Handbuch des Betreibers (AdminSuite)

---

## 9. Änderungen dieser Dokumentation

| Datum | Version | Änderung |
|---|---|---|
| 15.11.2026 | 1 | Erste Fassung |
| 15.11.2026 | 2 | Automatische Zuordnung von Bankumsätzen (2.3) |
| 16.11.2026 | 3 | Bankabruf über Enable Banking als zweiter Weg für Bankumsätze (2.3) |
