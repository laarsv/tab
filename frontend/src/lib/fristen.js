// Fälligkeit mit Werktag-Verschiebung (§ 193 BGB) — Spiegel von backend/app/services/fristen.py
// (Vorschau im Rechnungsformular; der Server rechnet beim Speichern selbst). Beide gemeinsam ändern.
// Es zählen nur bundesweite Feiertage; Landesfeiertage verschieben die Fälligkeit bewusst nicht.

export function addDays(iso, tage) {
  const d = new Date(`${iso}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + tage);
  return d.toISOString().slice(0, 10);
}

export function tageZwischen(von, bis) {
  return Math.round((Date.parse(`${bis}T00:00:00Z`) - Date.parse(`${von}T00:00:00Z`)) / 86_400_000);
}

// Gaußsche Osterformel (anonymer gregorianischer Algorithmus) -> ISO-Datum.
function ostersonntag(jahr) {
  const a = jahr % 19;
  const b = Math.floor(jahr / 100);
  const c = jahr % 100;
  const d = Math.floor(b / 4);
  const e = b % 4;
  const f = Math.floor((b + 8) / 25);
  const g = Math.floor((b - f + 1) / 3);
  const h = (19 * a + b - d - g + 15) % 30;
  const i = Math.floor(c / 4);
  const k = c % 4;
  const l = (32 + 2 * e + 2 * i - h - k) % 7;
  const m = Math.floor((a + 11 * h + 22 * l) / 451);
  const monat = Math.floor((h + l - 7 * m + 114) / 31);
  const tag = ((h + l - 7 * m + 114) % 31) + 1;
  return `${jahr}-${String(monat).padStart(2, '0')}-${String(tag).padStart(2, '0')}`;
}

function feiertageBundesweit(jahr) {
  const ostern = ostersonntag(jahr);
  return new Set([
    `${jahr}-01-01`,
    addDays(ostern, -2), // Karfreitag
    addDays(ostern, 1), // Ostermontag
    `${jahr}-05-01`,
    addDays(ostern, 39), // Christi Himmelfahrt
    addDays(ostern, 50), // Pfingstmontag
    `${jahr}-10-03`,
    `${jahr}-12-25`,
    `${jahr}-12-26`,
  ]);
}

function istArbeitsfrei(iso) {
  const wochentag = new Date(`${iso}T00:00:00Z`).getUTCDay(); // 0 = So, 6 = Sa
  return wochentag === 0 || wochentag === 6 || feiertageBundesweit(Number(iso.slice(0, 4))).has(iso);
}

export function naechsterWerktag(iso) {
  let tag = iso;
  while (istArbeitsfrei(tag)) tag = addDays(tag, 1);
  return tag;
}

// Rechnungsdatum + Zahlungsziel; bei Ziel 0 (sofort) ohne Verschiebung.
export function faelligkeit(datum, tage) {
  const ende = addDays(datum, tage);
  return tage === 0 ? ende : naechsterWerktag(ende);
}
