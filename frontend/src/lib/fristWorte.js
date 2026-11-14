import { tageZwischen } from './fristen.js';
import { todayISO } from './format.js';

// Fristen in Worten (wie vrwb_flow): „fällig in 3 Wochen“, „34 Tage überfällig“. Das Datum bleibt der Tooltip.
// Bis 13 Tage in Tagen, bis 9 Wochen in Wochen, dann Monate, ab 2 Jahren Jahre. Für Verzugstage, die rechtlich
// zählen (Mahnwesen), weiter die genaue Zahl der Tage verwenden.

// fall: 'nom' („3 Wochen überfällig“) | 'dat' („in 3 Wochen“)
export function dauer(tage, fall = 'nom') {
  const n = Math.abs(tage);
  const w = (zahl, eins, viele, vieleDat) => `${zahl} ${zahl === 1 ? eins : fall === 'dat' ? vieleDat : viele}`;
  if (n < 14) return w(n, 'Tag', 'Tage', 'Tagen');
  if (n < 63) return w(Math.round(n / 7), 'Woche', 'Wochen', 'Wochen');
  if (n < 730) return w(Math.round(n / 30.4), 'Monat', 'Monate', 'Monaten');
  return w(Math.round(n / 365), 'Jahr', 'Jahre', 'Jahren');
}

// -> { text, ueberfaellig, tage } ; tage < 0 = überfällig
export function fristInWorten(iso, heute = todayISO()) {
  const tage = tageZwischen(heute, iso);
  if (tage < 0) return { text: `${dauer(tage)} überfällig`, ueberfaellig: true, tage };
  if (tage === 0) return { text: 'heute fällig', ueberfaellig: false, tage };
  if (tage === 1) return { text: 'morgen fällig', ueberfaellig: false, tage };
  return { text: `fällig in ${dauer(tage, 'dat')}`, ueberfaellig: false, tage };
}
