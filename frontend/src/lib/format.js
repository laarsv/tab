// Geld in Cent (Integer) <-> deutsche Euro-Darstellung.

export function formatEuro(cent, withSymbol = true) {
  const v = (Number(cent) || 0) / 100;
  const s = v.toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return withSymbol ? `${s} €` : s;
}

// "12,34" oder "12.34" oder "1.234,56" -> Cent. Gibt null bei ungültig zurück.
export function parseEuroToCent(input) {
  if (input === null || input === undefined) return null;
  let s = String(input).trim().replace(/\s|€/g, '');
  if (!s) return null;
  if (s.includes(',')) {
    // deutsches Format: Punkt = Tausender, Komma = Dezimal
    s = s.replace(/\./g, '').replace(',', '.');
  }
  const num = Number(s);
  if (!Number.isFinite(num)) return null;
  return Math.round(num * 100);
}

// Cent -> Eingabewert "12,34" (für Edit-Formulare)
export function centToInput(cent) {
  if (cent === null || cent === undefined) return '';
  return ((Number(cent) || 0) / 100).toFixed(2).replace('.', ',');
}

export function formatDateDE(iso) {
  if (!iso) return '';
  return `${iso.slice(8, 10)}.${iso.slice(5, 7)}.${iso.slice(0, 4)}`;
}

export function todayISO() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
