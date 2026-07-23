// Abo-Intervalle: Stichtag + Intervall mit Monatsende-Klemmung (31.01. + 1M -> 28./29.02.)
// — Spiegel der Backend-Logik in services/abo.py (naechster_termin).

export const INTERVALL_MONATE = { monatlich: 1, vierteljaehrlich: 3, jaehrlich: 12 };

export const INTERVALL_LABELS = {
  monatlich: 'monatlich',
  vierteljaehrlich: 'vierteljährlich',
  jaehrlich: 'jährlich',
};

export function naechsterTermin(isoDatum, intervall) {
  const [j, m, t] = isoDatum.split('-').map(Number);
  const monate = INTERVALL_MONATE[intervall] || 1;
  const gesamt = m - 1 + monate;
  const jahr = j + Math.floor(gesamt / 12);
  const monat = (gesamt % 12) + 1;
  const letzterTag = new Date(jahr, monat, 0).getDate();
  const tag = Math.min(t, letzterTag);
  return `${jahr}-${String(monat).padStart(2, '0')}-${String(tag).padStart(2, '0')}`;
}
