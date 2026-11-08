import { api } from '../api/client.js';

// Neuigkeiten („Was ist neu?"). Bei jedem größeren Feature hier einen Eintrag
// ERGÄNZEN (id hochzählen, neueste zuerst) — das Fenster öffnet sich dann beim
// nächsten Login automatisch. Gelesen-Status liegt je Account auf dem Server (s. u.).

export const NEUIGKEITEN = [
  {
    id: 30,
    datum: '2026-11-08',
    titel: 'Neue Startseite: die Übersicht',
    text: 'Nach dem Login landest du jetzt auf der Übersicht. Oben stehen Einnahmen, Ausgaben und Saldo des Jahres mit dem Vorjahr zum Vergleich, dazu deine offenen Forderungen und der Umsatz nach § 19 mit den Grenzen. Darunter sammelt „Zu erledigen“, was gerade wartet: überfällige Rechnungen, dringende Steuerfristen, fällige Dauerbelege, Belege im Eingang, Bankumsätze ohne Zuordnung, Rechnungsentwürfe, Angebote ohne Antwort und ein noch nicht abgeschlossenes Vorjahr. Jede Zeile hat einen Knopf, der direkt an die richtige Stelle führt. Darunter siehst du die offenen Rechnungen und deine letzten Buchungen. Am Handy ist die Übersicht der erste Reiter unten.',
  },
  {
    id: 29,
    datum: '2026-11-08',
    titel: 'GWG-Grenze korrigiert: 800 € inklusive USt',
    text: 'Bisher stand in Tab, ein geringwertiges Wirtschaftsgut (GWG) dürfe bis 800 € netto, also etwa 952 € brutto, sofort abgesetzt werden. Für Kleinunternehmer ist das zu großzügig: Wer keine Vorsteuer abziehen kann, rechnet mit dem gezahlten Betrag, die Grenze liegt also bei 800 € inklusive USt. Tab nennt jetzt überall 800 € und warnt im Buchungsfenster, sobald ein GWG darüber liegt. Wenn du eine Anschaffung zwischen 800 und 952 € als GWG gebucht hast, lege sie besser unter „Abschreibungen“ an (oder wähle dort den Sammelposten). Bei Zweifeln im Einzelfall hilft die Steuerberatung.',
  },
  {
    id: 28,
    datum: '2026-11-08',
    titel: 'Mehr Abschreibungsmethoden bei der AfA',
    text: 'Unter „Abschreibungen“ wählst du jetzt die Methode: linear wie bisher, degressiv (für Anschaffungen vom 01.07.2025 bis 31.12.2027 bis zu 30 %, Tab wechselt von selbst zur linearen AfA, sobald sie höher ist), die Staffel für Elektrofahrzeuge (75/10/5/5/3/2 %) und den Sammelposten für Anschaffungen von 250,01 bis 1.000 € (je ein Fünftel in fünf Jahren). Tab zeigt dir beim Anlegen den kompletten Plan mit dem Restwert je Jahr und bietet nur Methoden an, die für das Datum gelten. Bestehende Anlagen bleiben linear und rechnen wie vorher. Die gewählte Methode steht im Journal. Welche Methode für dich sinnvoll ist, klärst du im Zweifel mit der Steuerberatung.',
  },
  {
    id: 27,
    datum: '2026-11-08',
    titel: 'Dauerbelege und Privatanteil',
    text: 'Neue Seite „Dauerbelege“: Miete, Versicherung, Leasing oder ein Abo legst du einmal an (Betrag, Kategorie, Rhythmus). Tab zeigt jeden Termin als fällig, und du buchst ihn mit einem Klick — oder ordnest die Abbuchung im Bank-Import zu, dort schlägt Tab den passenden Dauerbeleg vor. Tab bucht nie von selbst; mit „Alle buchen“ holst du verpasste Termine nach, und einen mietfreien Monat überspringst du. Neu am Buchungsfenster: „Auch privat genutzt“ bei Ausgaben, z. B. 20 % für das Handy. Gezahlt wird der volle Betrag, als Betriebsausgabe zählt nur der betriebliche Teil (Summenblatt, Kennzahlen, Jahres-Check). Tab merkt sich den Anteil je Kategorie und schlägt ihn beim nächsten Mal vor. Das Journal enthält zwei neue Spalten am Ende: Privatanteil und betrieblicher Betrag.',
  },
  {
    id: 26,
    datum: '2026-11-08',
    titel: 'Angebote schreiben und in Rechnungen umwandeln',
    text: 'Neuer Reiter „Angebote“ bei den Rechnungen: Du schreibst ein Angebot mit eigener Nummer (AN-Jahr-0001), Gültigkeit und optionalen Positionen — Zusatzleistungen, die der Kunde dazubuchen kann und die nicht in der Angebotssumme stehen. Tab erzeugt das PDF und schickt es auf Wunsch per Mail. Sagt der Kunde zu, wandelst du das Angebot mit einem Klick in einen Rechnungsentwurf um, optionale Positionen nach Wahl; das Angebot gilt danach als angenommen und abgerechnet. Abgelaufene Angebote erkennt Tab selbst, ein versendetes Angebot lässt sich als neuer Entwurf kopieren. Angebote sind kein EÜR-Eintrag: gebucht wird erst, was zufließt.',
  },
  {
    id: 25,
    datum: '2026-11-08',
    titel: 'Teilzahlungen und Skonto bei Rechnungen',
    text: 'Eine Rechnung kann jetzt in Raten bezahlt werden: Mit „Zahlung erfassen“ trägst du Datum und Betrag ein, Tab bucht den Eingang als Einnahme und zeigt, was noch offen ist. Den Rest kannst du als Skonto oder Forderungsausfall ausbuchen — beides ist kein Einkommen und wird nicht gebucht. Neu im Rechnungsformular: Skonto (Prozent und Frist), das auch auf dem PDF und in der E-Rechnung steht. Im Bank-Import erkennt Tab Skonto-Zahlungen und Teilbeträge und fragt, was mit dem Rest passieren soll; Mahnungen und Verzugszinsen rechnen mit dem offenen Rest.',
  },
  {
    id: 24,
    datum: '2026-11-08',
    titel: 'Neue Seite: Bank',
    text: 'Importiere deinen Kontoauszug als CAMT.053 (XML) oder CSV und ordne jeden Umsatz zu: Tab erkennt DKB, Sparkasse und andere CSV-Formate, schlägt zu Eingängen die passende offene Rechnung vor (Betrag, Rechnungsnummer, Name) und bucht sie mit einem Klick als bezahlt. Ausgaben buchst du mit dem Umsatz vorbelegt, auf Wunsch mit einem passenden Beleg aus dem Eingang; Privates ignorierst du. Eine Datei kannst du beliebig oft importieren, schon vorhandene Umsätze erkennt Tab. Tab ruft dein Konto nicht ab — die Datei kommt von dir.',
  },
  {
    id: 23,
    datum: '2026-11-08',
    titel: 'Jahresabschluss: Jahr sperren und versiegeln',
    text: 'Unter „Jahresabschluss“ kannst du ein beendetes Jahr abschließen: Danach sind Buchungen, Belege, AfA und Fahrten dieses Jahres gesperrt und Tab versiegelt die Daten. Jede Änderung in Tab steht jetzt in einem Änderungsprotokoll, das als Hash-Kette gegen nachträgliches Ändern gesichert ist — mit „Alles prüfen“ rechnest du alles nach. Wieder öffnen geht nur mit Begründung. Das Jahresarchiv enthält jetzt Prüfsummen (pruefsummen.sha256), das Protokoll und einen Prüfwert, den du außerhalb des Servers aufbewahren solltest. Das ist Nachvollziehbarkeit, keine Zertifizierung und keine Steuerberatung.',
  },
  {
    id: 22,
    datum: '2026-11-08',
    titel: 'Neue Seite: Fristen',
    text: 'Unter „Fristen" siehst du die Termine für deine Steuererklärung: die Abgabe der Einkommensteuererklärung mit Anlage EÜR je Jahr (31. Juli des Folgejahres) und auf Wunsch die Einkommensteuer-Vorauszahlungen. Offenes aus der Vergangenheit bleibt stehen, bis du es abhakst; in der Seitenleiste zeigt eine Zahl, was überfällig oder bald dran ist. Mit dem Kalender-Abo landen die Fristen samt Erinnerung (3 Tage vorher und am Morgen) in deinem Handy- oder Computerkalender. Tab überträgt nichts ans Finanzamt, und mit Steuerberatung gelten längere Fristen.',
  },
  {
    id: 21,
    datum: '2026-11-08',
    titel: 'GiroCode auf Rechnung und Mahnung',
    text: 'Rechnungen und Mahnungen tragen jetzt einen GiroCode: Dein Kunde scannt ihn mit der Banking-App, und die Überweisung ist mit IBAN, Betrag und Rechnungsnummer ausgefüllt. Voraussetzung ist deine IBAN beim Gewerbe. Dort kannst du auch den Kontoinhaber eintragen — Banken prüfen beim Überweisen, ob der Empfängername zum Konto passt. Bezahlte und stornierte Rechnungen bekommen keinen Code. Außerdem behoben: Sehr lange Rechnungen rissen eine Position über den Seitenumbruch, und die Mahnung grüßte mit dem internen Gewerbe-Namen statt mit deinem Namen.',
  },
  {
    id: 20,
    datum: '2026-11-08',
    titel: 'Fälligkeit und Mahnwesen',
    text: 'Jede Rechnung hat jetzt ein Zahlungsziel (Standard 14 Tage, beim Gewerbe einstellbar) und trägt ihre Fälligkeit im PDF und in der E-Rechnung. Überfällige Rechnungen siehst du an der Seitenleiste und im neuen Reiter „Mahnwesen“: Zahlungserinnerung, 1. Mahnung und letzte Mahnung mit PDF, Mail-Versand, optionaler Mahngebühr, Verzugspauschale und Verzugszinsen. Den Basiszinssatz holst du beim Gewerbe mit einem Klick bei der Bundesbank. Wiederkehrende Rechnungen haben einen eigenen Reiter. Außerdem behoben: Ein Gedankenstrich oder typografische Anführungszeichen in einer Position ließen die PDF-Erstellung scheitern. Hinweis: Rechnungen aus der Zeit vor diesem Update haben kein Zahlungsziel; sie gelten 30 Tage nach dem Rechnungsdatum als überfällig, solange sie nicht als bezahlt markiert sind.',
  },
  {
    id: 19,
    datum: '2026-11-01',
    titel: 'Anlage EÜR 2026 ist da',
    text: 'Der amtliche Vordruck 2026 ist eingearbeitet: Der Export für 2026 nutzt jetzt die richtigen Zeilen (neue Zeile 27, dadurch rücken viele Zeilen um eins nach hinten) und ist nicht mehr „vorläufig". Neu: Die Entfernungspauschale beträgt ab 2026 0,38 € ab dem ersten Kilometer — der Rechner kennt das.',
  },
  {
    id: 18,
    datum: '2026-10-27',
    titel: 'Neues Design mit Seitenleiste',
    text: 'Tab hat jetzt eine Royal-Seitenleiste wie vrwb_recap: Navigation, Gewerbe, Jahr und dein Beleg-Eingang sind immer griffbereit, alle Seiten stehen als ruhige Zeilen da. Am Handy gibt es oben eine schmale Leiste, unten die Tabs und das Menü als Schublade.',
  },
  {
    id: 17,
    datum: '2026-10-27',
    titel: 'Einnahme oder Ausgabe — erkennt Tab selbst',
    text: 'Beim Verbuchen eines Belegs liest Tab jetzt auch heraus, ob es eine Einnahme oder eine Ausgabe ist, und zeigt dann nur die passenden Kategorien. Lag die Erkennung daneben, schaltest du oben im Fenster mit einem Klick um.',
  },
  {
    id: 16,
    datum: '2026-07-22',
    titel: 'Anmelden auch ohne Google',
    text: 'Registrieren geht jetzt klassisch mit E-Mail und Passwort — Bestätigungscode kommt per Mail, Passwort-Reset inklusive. Der Google-Login bleibt natürlich bestehen.',
  },
  {
    id: 15,
    datum: '2026-07-22',
    titel: 'Tab ist offen für alle',
    text: 'Jedes Google-Konto kann sich jetzt anmelden und loslegen — Freunde und Kollegen einfach auf tab.vrwb.de schicken. Jeder Nutzer hat seinen komplett eigenen Bereich.',
  },
  {
    id: 14,
    datum: '2026-07-22',
    titel: 'Eigener Mail-Server statt Gmail',
    text: 'Deine Mail liegt nicht bei Google? Im Mail-Dialog jetzt „Eigener Mail-Server" wählen (z. B. All-Inkl, IONOS): Rechnungen gehen dann von deiner eigenen Domain raus, und der Beleg-Import holt dort ab.',
  },
  {
    id: 13,
    datum: '2026-07-22',
    titel: 'Getrennte Bereiche für jeden Nutzer',
    text: 'Jedes Gewerbe gehört jetzt der Person, die es angelegt hat — Buchungen, Belege, Rechnungen und Kontakte sind privat. Andere Nutzer dieser Tab-Instanz sehen deine Daten nicht mehr (und du ihre nicht).',
  },
  {
    id: 12,
    datum: '2026-07-22',
    titel: 'Deine Rechnungen sind jetzt E-Rechnungen',
    text: 'Jede Rechnungs-PDF trägt ab sofort unsichtbar das amtliche E-Rechnungs-XML in sich (ZUGFeRD/EN 16931). Für deine Kunden sieht alles aus wie immer — deren Buchhaltungssoftware liest die Daten aber automatisch ein. Als Kleinunternehmer wärst du dazu nicht mal verpflichtet: einfach einen Schritt voraus.',
  },
  {
    id: 11,
    datum: '2026-07-22',
    titel: 'Belege per E-Mail einschicken',
    text: 'Leite Rechnungen einfach an deine persönliche +tab-Adresse weiter (z. B. name+tab@gmail.com) — Tab holt sie alle 10 Minuten ab und legt die Anhänge in den Beleg-Eingang. Nur Mails von freigeschalteten Absendern werden importiert.',
    link: { to: '/einrichtung', label: 'Einrichten' },
  },
  {
    id: 10,
    datum: '2026-07-22',
    titel: 'Tab aufs Handy — installieren & teilen',
    text: 'Tab lässt sich als App installieren. Auf Android taucht es danach im Teilen-Menü auf: Kassenzettel fotografieren → Teilen → tab → liegt im Eingang. iPhone: App installieren geht auch, fürs Teilen nutzt du dort den Mail-Weg.',
    link: { to: '/einrichtung', label: 'Anleitung' },
  },
  {
    id: 9,
    datum: '2026-07-22',
    titel: 'Belege werden automatisch gelesen',
    text: 'Beim Verbuchen füllt Tab Datum, Betrag, Lieferant und Kategorie vor: E-Rechnungen exakt, PDF-Rechnungen über den Text, Fotos per Texterkennung. Die Kategorie lernt aus deinen früheren Buchungen. Alles lokal auf deinem Server — und immer nur ein Vorschlag zum Prüfen.',
  },
  {
    id: 8,
    datum: '2026-07-22',
    titel: 'Fälligkeit im Beleg-Eingang',
    text: 'Offene Rechnungen bekommen ein „fällig am"-Datum — der Eingang sortiert das Dringendste nach oben und markiert Überfälliges rot. Bezahlen, verbuchen, fertig.',
  },
  {
    id: 7,
    datum: '2026-07-22',
    titel: 'Kontakte, die sich selbst pflegen',
    text: 'Jede Rechnung merkt sich ihren Empfänger automatisch. Bei der nächsten Rechnung reicht „Aus Kontakten übernehmen" — Name, Anschrift und E-Mail sind drin.',
  },
  {
    id: 6,
    datum: '2026-07-22',
    titel: 'Wiederkehrende Rechnungen (Abos)',
    text: 'An jeder Rechnung gibt es „Wiederholen…": monatlich, vierteljährlich oder jährlich erstellt Tab die Rechnung automatisch — als Entwurf oder direkt versendet. Der Platzhalter {monat} wird z. B. zu „Betreuung 08/2026".',
  },
  {
    id: 5,
    datum: '2026-07-14',
    titel: 'Rechnungen schreiben & versenden',
    text: 'Rechnungen mit fortlaufender Nummer und allen Pflichtangaben (§19- oder §4-Nr.-11-Hinweis wählbar), als PDF und per E-Mail von deiner eigenen Adresse. Bezahlte Rechnungen wandern per Klick als Einnahme in die EÜR.',
  },
  {
    id: 4,
    datum: '2026-07-14',
    titel: 'Jahres-Check: nichts mehr vergessen',
    text: 'Die häufigsten Absetz-Themen als einfache Fragen — Auto, Handy, Homeoffice, Bewirtung … Der Status kommt automatisch aus deinen Buchungen, dazu die Liste „Gehört NICHT in die Buchhaltung".',
    link: { to: '/check', label: 'Jahres-Check öffnen' },
  },
  {
    id: 3,
    datum: '2026-07-14',
    titel: 'Fahrten-Liste & Firmenwagen',
    text: 'Betriebliche Fahrten mit dem Privatwagen unterm Jahr sammeln und am Jahresende per Klick als km-Pauschale buchen. Für den Firmenwagen rechnet die 1 %-Regelung mit — inkl. 0,5 % (Hybrid) und 0,25 % (E-Auto).',
    link: { to: '/fahrten', label: 'Fahrten-Liste' },
  },
  {
    id: 2,
    datum: '2026-07-13',
    titel: 'Komfort überall',
    text: 'Beleg-Eingang mit „Jetzt abarbeiten"-Wizard, Suche und Filter in den Buchungen, Buchung duplizieren, CSV-Import für Altdaten, Rechner für Homeoffice/Verpflegung/Entfernungspauschale und das Jahres-Archiv (ZIP) mit allen Belegen.',
  },
];

// Gelesen-Status je Eintrag (Set von IDs), je ACCOUNT auf dem Server (/api/news) —
// localStorage ist nur Cache/Offline-Fallback, sonst käme das Fenster auf jedem
// Gerät/Browser/in der PWA wieder. Das Fenster zeigt Ungelesenes so lange, bis es
// einzeln (oder per „Alle als gelesen") bestätigt wird — bloßes Schließen zählt
// NICHT als gelesen.
const LS_PREFIX = 'tab_news_gelesen'; // + ':' + E-Mail (je Login getrennt)
const LS_ALT = 'tab_news_gesehen'; // altes Format: höchste gesehene id

const bekannt = new Set(NEUIGKEITEN.map((n) => n.id));

function leseJson(key) {
  try {
    const arr = JSON.parse(localStorage.getItem(key) || '[]');
    return Array.isArray(arr) ? arr : [];
  } catch {
    return [];
  }
}

// Lokaler Cache; übernimmt beim ersten Mal die alten, nicht login-bezogenen Schlüssel.
export function gelesenIds(email) {
  const set = new Set([...leseJson(`${LS_PREFIX}:${email}`), ...leseJson(LS_PREFIX)]);
  try {
    const alt = Number(localStorage.getItem(LS_ALT) || 0);
    if (alt) NEUIGKEITEN.forEach((n) => n.id <= alt && set.add(n.id));
  } catch {
    /* localStorage gesperrt (z. B. privater Modus) — dann zählt nur der Server */
  }
  return set;
}

function schreibeLokal(email, set) {
  try {
    localStorage.setItem(`${LS_PREFIX}:${email}`, JSON.stringify([...set]));
  } catch {
    /* siehe oben — Server bleibt die Quelle der Wahrheit */
  }
}

// Server-Stand laden und mit dem lokalen vereinigen (lokal Gelesenes, das dem Server
// noch fehlt, wird nachgetragen — so nimmt jedes Gerät seinen Stand mit). Schlägt der
// Server fehl, gilt der lokale Stand.
export async function syncGelesen(email) {
  const lokal = gelesenIds(email);
  try {
    const { data } = await api.get('/api/news');
    const server = new Set(data.gelesen);
    const fehlt = [...lokal].filter((id) => bekannt.has(id) && !server.has(id));
    if (fehlt.length) await api.post('/api/news/gelesen', { ids: fehlt });
    const alle = new Set([...lokal, ...server]);
    schreibeLokal(email, alle);
    return alle;
  } catch {
    return lokal;
  }
}

// Einträge als gelesen markieren: lokal sofort, Server best effort (der nächste
// syncGelesen trägt Fehlendes nach). Gibt den neuen Gesamtstand zurück.
export function markiereGelesen(email, ids) {
  const set = gelesenIds(email);
  ids.forEach((id) => set.add(id));
  schreibeLokal(email, set);
  api.post('/api/news/gelesen', { ids }).catch(() => {});
  return set;
}

export function ungelesene(gelesen) {
  return NEUIGKEITEN.filter((n) => !gelesen.has(n.id)).length;
}
