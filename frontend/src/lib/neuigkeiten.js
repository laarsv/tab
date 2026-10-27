import { api } from '../api/client.js';

// Neuigkeiten („Was ist neu?"). Bei jedem größeren Feature hier einen Eintrag
// ERGÄNZEN (id hochzählen, neueste zuerst) — das Fenster öffnet sich dann beim
// nächsten Login automatisch. Gelesen-Status liegt je Account auf dem Server (s. u.).

export const NEUIGKEITEN = [
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
