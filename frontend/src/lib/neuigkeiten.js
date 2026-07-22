// Neuigkeiten („Was ist neu?"). Bei jedem größeren Feature hier einen Eintrag
// ERGÄNZEN (id hochzählen, neueste zuerst) — das Fenster öffnet sich dann beim
// nächsten Login automatisch. Gesehen-Status liegt in localStorage.

export const NEUIGKEITEN = [
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

const LS_KEY = 'tab_news_gesehen';

export function neuesteId() {
  return Math.max(...NEUIGKEITEN.map((n) => n.id));
}

export function gesehenBis() {
  return Number(localStorage.getItem(LS_KEY) || 0);
}

export function ungelesene() {
  const bis = gesehenBis();
  return NEUIGKEITEN.filter((n) => n.id > bis).length;
}

export function alleGesehen() {
  localStorage.setItem(LS_KEY, String(neuesteId()));
}
