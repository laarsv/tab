// Besteuerung je Gewerbe und Jahr — Spiegel von backend/app/services/besteuerung.py und rechnung_summen.py
// (beide gemeinsam ändern). Das Gewerbe aus /api/gewerbe trägt `besteuerung_wechsel` [{ab_jahr, art}];
// es gilt der letzte Wechsel <= Jahr, ohne Eintrag Kleinunternehmer (EUER_KATEGORIEN.md §8).

export const KU = 'kleinunternehmer';
export const REGEL = 'regelbesteuerung';

export function artImJahr(gewerbe, jahr) {
  const j = Number(jahr);
  const passend = (gewerbe?.besteuerung_wechsel || []).filter((w) => w.ab_jahr <= j);
  if (!passend.length) return KU;
  return passend.reduce((a, b) => (b.ab_jahr > a.ab_jahr ? b : a)).art;
}

export function istRegel(gewerbe, jahr) {
  return artImJahr(gewerbe, jahr) === REGEL;
}

export const ART_LABEL = { [KU]: 'Kleinunternehmer', [REGEL]: 'Regelbesteuerung' };

// Steuersätze (Basispunkte) für Dropdowns
export const SAETZE = [
  { value: '1900', label: '19 %' },
  { value: '700', label: '7 %' },
  { value: '0', label: '0 %' },
];

// Zahlungen ans/vom Finanzamt haben selbst keinen Steuersatz
export const OHNE_SATZ = new Set(['ust_zahlung', 'ust_erstattung']);

// Steuer im Bruttobetrag: brutto × Satz / (100 % + Satz), kaufmännisch gerundet
export function ustAusBrutto(bruttoCent, bp) {
  if (!bp || !(bruttoCent > 0)) return 0;
  const nenner = 10000 + bp;
  return Math.floor((2 * bruttoCent * bp + nenner) / (2 * nenner));
}

// Steuer auf einen Nettobetrag, kaufmännisch gerundet
export function ustAufNetto(nettoCent, bp) {
  if (!bp) return 0;
  const z = nettoCent * bp;
  const vz = z < 0 ? -1 : 1;
  return vz * Math.floor((2 * Math.abs(z) + 10000) / 20000);
}

// Summen von Rechnungs-/Angebotspositionen: Steuer je Satz auf die Netto-Summe des Satzes (EN 16931)
export function positionsSummen(positionen) {
  const jeSatz = new Map();
  for (const p of positionen) {
    const netto = Math.round((Number(p.menge) || 0) * (Number(p.einzelpreis_cent) || 0));
    const satz = Number(p.ust_bp) || 0;
    jeSatz.set(satz, (jeSatz.get(satz) || 0) + netto);
  }
  const gruppen = [...jeSatz.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([satz, netto]) => ({ ust_bp: satz, netto_cent: netto, ust_cent: ustAufNetto(netto, satz) }));
  const netto = gruppen.reduce((s, g) => s + g.netto_cent, 0);
  const ust = gruppen.reduce((s, g) => s + g.ust_cent, 0);
  return { netto_cent: netto, ust_cent: ust, brutto_cent: netto + ust, je_satz: gruppen, mit_ust: gruppen.some((g) => g.ust_bp) };
}

export function satzText(bp) {
  return `${(Number(bp) || 0) / 100} %`.replace('.', ',');
}

// Steuer-Hinweis auf Rechnung/Angebot/Abo. Bei Regelbesteuerung wird USt ausgewiesen („regel“, kein Text);
// § 4 Nr. 11 begründet dann Positionen mit 0 %. Der Server normalisiert ku19 <-> regel je Jahr.
export function steuerhinweisOptionen(regel) {
  return regel
    ? [
        { value: 'regel', label: 'Umsatzsteuer wird ausgewiesen (Standard)' },
        { value: 'vers4nr11', label: 'Mit Positionen zu 0 %: steuerfrei § 4 Nr. 11 UStG (Versicherungsprovision)' },
      ]
    : [
        { value: 'ku19', label: 'Kleinunternehmer § 19 UStG (Standard)' },
        { value: 'vers4nr11', label: 'Steuerfrei § 4 Nr. 11 UStG (Versicherungsprovision)' },
      ];
}

// Hinweis-Wert passend zur Art des Jahres
export function hinweisFuer(hinweis, regel) {
  if (regel && (!hinweis || hinweis === 'ku19')) return 'regel';
  if (!regel && (!hinweis || hinweis === 'regel')) return 'ku19';
  return hinweis;
}
