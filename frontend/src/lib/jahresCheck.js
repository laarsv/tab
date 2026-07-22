// Jahres-Check: die häufigsten Absetz-Themen für Einsteiger, einmal pro Jahr
// durchgehen. Buchungs-Themen führen in eine vorausgefüllte Buchung; der Status
// kommt automatisch aus den echten Buchungen des Jahres. Info-Themen (info: true)
// haben keine Kategorie und werden per „Erledigt"-Haken abgehakt.
// „Nicht relevant" + „Erledigt" liegen pro Gewerbe+Jahr in localStorage.

export const TOPICS = [
  {
    key: 'einnahmen',
    frage: 'Hast du alle Einnahmen erfasst?',
    text: 'Alles, was reingekommen ist: Rechnungen an Kunden, App-Erlöse, Auszahlungen von Plattformen. Brutto buchen, Datum = Tag der Zahlung.',
    aktionen: [{ label: 'Einnahme buchen', katKey: 'einnahme_ku' }],
  },
  {
    key: 'auto',
    frage: 'Bist du beruflich unterwegs — Auto, Bahn oder Bus?',
    text: 'Privatwagen: betriebliche Kilometer in der Fahrten-Liste sammeln und mit 0,30 €/km buchen. Firmenwagen (gehört dem Betrieb): laufende Kosten buchen und die Privatnutzung über die 1 %-Regelung erfassen (E-Auto 0,25 %, Hybrid 0,5 %). Bahn-, Bus- und Taxi-Tickets für Geschäftsfahrten laufen über die eigene ÖPNV-Kategorie (Deutschlandticket: nur den betrieblichen Anteil). E-Auto-Fahrer: Auch die jährliche THG-Prämie ist eine Betriebseinnahme!',
    aktionen: [
      { label: 'km-Pauschale (Privatwagen)', katKey: 'fahrtkosten_kfz' },
      { label: 'ÖPNV/Bahn/Taxi buchen', katKey: 'oepnv' },
      { label: '1 %-Regelung (Firmenwagen)', katKey: 'kfz_privatnutzung' },
      { label: 'Kfz-Kosten (Firmenwagen)', katKey: 'kfz_kosten' },
    ],
    links: [{ to: '/fahrten', label: 'Fahrten-Liste öffnen' }],
  },
  {
    key: 'handy',
    frage: 'Nutzt du Handy oder Internet auch beruflich?',
    text: 'Den betrieblichen Anteil ansetzen — bei gemischter Nutzung sind pauschal 50 % üblich. Am einfachsten: einmal im Monat oder einmal fürs ganze Jahr buchen.',
    aktionen: [{ label: 'Telefon/Internet buchen', katKey: 'telekommunikation' }],
  },
  {
    key: 'homeoffice',
    frage: 'Arbeitest du von zuhause?',
    text: 'Homeoffice-Pauschale: 6 € pro Tag, max. 210 Tage (1.260 €) im Jahr — der Rechner in der Buchung macht das für dich. Ein echtes, abgeschlossenes Arbeitszimmer geht alternativ mit Jahrespauschale (1.260 €) oder tatsächlichen Kosten.',
    aktionen: [
      { label: 'Homeoffice-Tage buchen', katKey: 'homeoffice_pauschale' },
      { label: 'Arbeitszimmer buchen', katKey: 'arbeitszimmer' },
    ],
  },
  {
    key: 'technik',
    frage: 'Hast du Technik oder Arbeitsmittel gekauft?',
    text: 'Laptop, Monitor, Schreibtischstuhl … Bis 800 € netto (≈ 952 € brutto) als GWG sofort absetzen. Teurer? Dann über die Abschreibungs-Seite als Anschaffung anlegen — Computer-Hardware/Software darf mit 1 Jahr Nutzungsdauer sofort voll abgesetzt werden.',
    aktionen: [{ label: 'GWG buchen (≤ 800 € netto)', katKey: 'gwg' }],
    links: [{ to: '/afa', label: 'Abschreibung anlegen' }],
  },
  {
    key: 'software',
    frage: 'Zahlst du für Software, Cloud oder Hosting?',
    text: 'Abos wie Adobe, Canva, Google Workspace, Server, Domains, App-Store-Gebühren — alles voll absetzbar.',
    aktionen: [{ label: 'Software/Hosting buchen', katKey: 'software_hosting' }],
  },
  {
    key: 'konto',
    frage: 'Zahlst du Kontoführung oder Zahlungsgebühren?',
    text: 'Geschäftskonto-Gebühren, PayPal-, Stripe- oder Kartenlese-Gebühren — kleine Beträge, läppern sich übers Jahr. Tipp: einmal im Jahr aus dem Konto-/PayPal-Jahresreport summieren.',
    aktionen: [{ label: 'Gebühren buchen', katKey: 'kontogebuehren' }],
  },
  {
    key: 'fortbildung',
    frage: 'Hast du Kurse, Bücher oder Fortbildungen bezahlt?',
    text: 'Onlinekurse, Seminare, Fachbücher, Coaching mit Berufsbezug — voll absetzbar.',
    aktionen: [{ label: 'Fortbildung buchen', katKey: 'fortbildung' }],
  },
  {
    key: 'versicherung',
    frage: 'Hast du betriebliche Versicherungen oder Beiträge?',
    text: 'Z. B. Betriebshaftpflicht, Vermögensschadenhaftpflicht, IHK-Beitrag, Berufsverband. Private Versicherungen (Kranken, Haftpflicht privat) gehören nicht hierher — siehe Kasten unten.',
    aktionen: [{ label: 'Versicherung/Beitrag buchen', katKey: 'versicherungen_betrieb' }],
  },
  {
    key: 'bewirtung',
    frage: 'Warst du mit Kunden oder Geschäftspartnern essen?',
    text: 'Geschäftsessen sind zu 70 % absetzbar — du buchst den vollen Betrag, den Rest rechnet Tab beim Export. Wichtig: Ort, Tag, Teilnehmer und Anlass gehören auf den Beleg.',
    aktionen: [{ label: 'Bewirtung buchen', katKey: 'bewirtung' }],
  },
  {
    key: 'reisen',
    frage: 'Warst du geschäftlich unterwegs?',
    text: 'Hotel und Reisenebenkosten laufen über Reisekosten. Fürs Essen unterwegs gibt es Pauschalen: 28 € pro vollem Tag, 14 € für An-/Abreisetage (> 8 h) — nicht die echten Restaurantbelege.',
    aktionen: [
      { label: 'Übernachtung/Nebenkosten buchen', katKey: 'reise_nebenkosten' },
      { label: 'Verpflegungspauschale buchen', katKey: 'verpflegungsmehraufwand' },
    ],
  },
  {
    key: 'geschenke',
    frage: 'Hast du Kunden etwas geschenkt?',
    text: 'Bis 50 € pro Person und Jahr absetzbar — darüber leider gar nicht. Empfänger und Anlass auf dem Beleg notieren.',
    aktionen: [{ label: 'Geschenk buchen', katKey: 'geschenke' }],
  },
  {
    key: 'buero',
    frage: 'Bürobedarf, Porto oder sonstiger Kleinkram?',
    text: 'Druckerpapier, Stifte, Briefmarken, Versandmaterial — der Sammelposten für alles Kleine.',
    aktionen: [{ label: 'Bürobedarf buchen', katKey: 'buerobedarf' }],
  },
  {
    key: 'gruendung',
    frage: 'Hast du dieses Jahr gegründet?',
    text: 'Dann zählen auch Kosten VOR der Anmeldung: Gewerbeanmeldung, Beratung, Technik, Fahrten zu Ämtern — als „vorweggenommene Betriebsausgaben" ganz normal in den passenden Kategorien buchen (Datum = Zahltag, auch wenn er vor dem Start liegt).',
    info: true,
    aktionen: [],
  },
  {
    key: 'rechnungshinweis',
    frage: 'Steht der §19-Hinweis auf deinen Rechnungen?',
    text: 'Als Kleinunternehmer darfst du keine Umsatzsteuer ausweisen und brauchst den Satz „Kein Ausweis von Umsatzsteuer, da Kleinunternehmer gemäß §19 UStG" auf jeder Rechnung. Plus: fortlaufende Rechnungsnummer, dein Name/Anschrift, Empfänger, Datum, Leistung, Betrag.',
    info: true,
    aktionen: [],
  },
  {
    key: 'ruecklage',
    frage: 'Steuer-Rücklage gebildet?',
    text: 'Auf den Gewinn zahlst du Einkommensteuer — die zieht dir niemand automatisch ab. Faustregel: 25–30 % vom Gewinn auf ein separates Konto legen, dann tut der Steuerbescheid nicht weh.',
    info: true,
    aktionen: [],
  },
  {
    key: 'aufbewahrung',
    frage: 'Belege sicher aufbewahrt?',
    text: 'Buchungsbelege musst du 8 Jahre aufbewahren (bis vor Kurzem 10 — im Zweifel 10 nehmen). Am einfachsten: alle Belege hier in Tab hochladen und am Jahresende das Jahres-Archiv (ZIP) auf der Export-Seite sichern.',
    info: true,
    aktionen: [],
  },
];

// Klassische Anfängerfehler — Dinge, die NICHT in die EÜR gehören.
export const NICHT_ABSETZBAR = [
  ['Private Kranken- & Rentenversicherung', 'kommen in die Einkommensteuererklärung (Sonderausgaben), nicht in die EÜR.'],
  ['Einkommensteuer-Zahlungen & -Vorauszahlungen', 'sind Privatsache — nie Betriebsausgabe.'],
  ['Normale Kleidung', 'auch wenn du sie beruflich trägst (Anzug, Sneaker). Nur echte Arbeitskleidung zählt.'],
  ['Essen im Alltag', 'allein Mittagessen ist privat — absetzbar nur Bewirtung mit Geschäftspartnern oder Reise-Pauschalen.'],
  ['Bußgelder & Knöllchen', 'sind nie absetzbar, auch auf Dienstfahrt nicht.'],
];

// Anzahl offener Themen (keine Buchung im Jahr, nicht erledigt, nicht „nicht relevant")
// — für das Nav-Badge und die Fortschrittsanzeige.
export function countOffeneTopics(kategorien, buchungen, state) {
  const keyById = Object.fromEntries(kategorien.map((k) => [k.id, k.key]));
  const bebucht = new Set();
  for (const b of buchungen) {
    for (const p of b.positionen) {
      const key = keyById[p.kategorie_id];
      if (key) bebucht.add(key);
    }
  }
  return TOPICS.filter(
    (t) =>
      !state.nichtRelevant.has(t.key) &&
      !state.erledigt.has(t.key) &&
      !t.aktionen.some((a) => bebucht.has(a.katKey)),
  ).length;
}

const lsKey = (gewerbeId, jahr) => `tab_check_${gewerbeId}_${jahr}`;

export function loadCheckState(gewerbeId, jahr) {
  try {
    const raw = JSON.parse(localStorage.getItem(lsKey(gewerbeId, jahr)) || '[]');
    if (Array.isArray(raw)) {
      // Altes Format: nur nicht-relevant-Liste
      return { nichtRelevant: new Set(raw), erledigt: new Set() };
    }
    return {
      nichtRelevant: new Set(raw.nichtRelevant || []),
      erledigt: new Set(raw.erledigt || []),
    };
  } catch {
    return { nichtRelevant: new Set(), erledigt: new Set() };
  }
}

export function saveCheckState(gewerbeId, jahr, state) {
  localStorage.setItem(
    lsKey(gewerbeId, jahr),
    JSON.stringify({ nichtRelevant: [...state.nichtRelevant], erledigt: [...state.erledigt] }),
  );
}
