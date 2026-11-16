// Gewinnermittlung je Gewerbe und Jahr — Spiegel von backend/app/services/gewinnermittlung.py (beide gemeinsam ändern).
// Das Gewerbe aus /api/gewerbe trägt `gewinnermittlung_wechsel` [{ab_jahr, art}]; es gilt der letzte Wechsel <= Jahr,
// ohne Eintrag EÜR (BILANZ.md).

export const EUER = 'euer';
export const BILANZ = 'bilanz';

export function gwImJahr(gewerbe, jahr) {
  const j = Number(jahr);
  const passend = (gewerbe?.gewinnermittlung_wechsel || []).filter((w) => w.ab_jahr <= j);
  if (!passend.length) return EUER;
  return passend.reduce((a, b) => (b.ab_jahr > a.ab_jahr ? b : a)).art;
}

export function istBilanz(gewerbe, jahr) {
  return gwImJahr(gewerbe, jahr) === BILANZ;
}

export const GW_LABEL = { [EUER]: 'Einnahmen-Überschuss-Rechnung', [BILANZ]: 'Bilanz (Betriebsvermögensvergleich)' };
