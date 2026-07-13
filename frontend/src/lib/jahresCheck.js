// Jahres-Check: die häufigsten Absetz-Themen für Einsteiger, einmal pro Jahr
// durchgehen. Jedes Thema führt direkt in eine vorausgefüllte Buchung; der
// Status kommt automatisch aus den echten Buchungen des Jahres.
// „Nicht relevant" wird pro Gewerbe+Jahr in localStorage gemerkt.

export const TOPICS = [
  {
    key: 'einnahmen',
    frage: 'Hast du alle Einnahmen erfasst?',
    text: 'Alles, was reingekommen ist: Rechnungen an Kunden, App-Erlöse, Auszahlungen von Plattformen. Brutto buchen, Datum = Tag der Zahlung.',
    aktionen: [{ label: 'Einnahme buchen', katKey: 'einnahme_ku' }],
  },
  {
    key: 'auto',
    frage: 'Bist du beruflich mit dem Auto unterwegs?',
    text: 'Privatwagen: einfach betriebliche Kilometer sammeln und mit 0,30 €/km buchen. Firmenwagen (gehört dem Betrieb): laufende Kosten buchen und die Privatnutzung über die 1 %-Regelung erfassen.',
    aktionen: [
      { label: 'km-Pauschale (Privatwagen)', katKey: 'fahrtkosten_kfz' },
      { label: '1 %-Regelung (Firmenwagen)', katKey: 'kfz_privatnutzung' },
      { label: 'Kfz-Kosten (Firmenwagen)', katKey: 'kfz_kosten' },
    ],
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
    text: 'Homeoffice-Pauschale: 6 € pro Tag, max. 210 Tage (1.260 €) im Jahr — der Rechner in der Buchung macht das für dich. Ein echtes, abgeschlossenes Arbeitszimmer wäre die Alternative.',
    aktionen: [
      { label: 'Homeoffice-Tage buchen', katKey: 'homeoffice_pauschale' },
      { label: 'Arbeitszimmer buchen', katKey: 'arbeitszimmer' },
    ],
  },
  {
    key: 'technik',
    frage: 'Hast du Technik oder Arbeitsmittel gekauft?',
    text: 'Laptop, Monitor, Schreibtischstuhl … Bis 800 € netto (≈ 952 € brutto) als GWG sofort absetzen. Teurer? Dann über die AfA-Seite als Wirtschaftsgut anlegen — Computer-Hardware darf mit 1 Jahr Nutzungsdauer sofort voll abgesetzt werden.',
    aktionen: [{ label: 'GWG buchen (≤ 800 € netto)', katKey: 'gwg' }],
    afaLink: true,
  },
  {
    key: 'software',
    frage: 'Zahlst du für Software, Cloud oder Hosting?',
    text: 'Abos wie Adobe, Canva, Google Workspace, Server, Domains, App-Store-Gebühren — alles voll absetzbar.',
    aktionen: [{ label: 'Software/Hosting buchen', katKey: 'software_hosting' }],
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
    text: 'Z. B. Betriebshaftpflicht, Vermögensschadenhaftpflicht, IHK-Beitrag, Berufsverband. Private Versicherungen (Kranken, Haftpflicht privat) gehören nicht hierher.',
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
];

// Anzahl offener Themen (keine Buchung im Jahr + nicht als „nicht relevant" markiert)
// — für das Nav-Badge und die Fortschrittsanzeige.
export function countOffeneTopics(kategorien, buchungen, nichtRelevant) {
  const keyById = Object.fromEntries(kategorien.map((k) => [k.id, k.key]));
  const bebucht = new Set();
  for (const b of buchungen) {
    for (const p of b.positionen) {
      const key = keyById[p.kategorie_id];
      if (key) bebucht.add(key);
    }
  }
  return TOPICS.filter(
    (t) => !nichtRelevant.has(t.key) && !t.aktionen.some((a) => bebucht.has(a.katKey)),
  ).length;
}

const lsKey = (gewerbeId, jahr) => `tab_check_${gewerbeId}_${jahr}`;

export function loadNichtRelevant(gewerbeId, jahr) {
  try {
    return new Set(JSON.parse(localStorage.getItem(lsKey(gewerbeId, jahr)) || '[]'));
  } catch {
    return new Set();
  }
}

export function saveNichtRelevant(gewerbeId, jahr, set) {
  localStorage.setItem(lsKey(gewerbeId, jahr), JSON.stringify([...set]));
}
