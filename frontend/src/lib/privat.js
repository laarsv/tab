// Privatanteil bei Ausgaben — Spiegel von backend/app/services/privatanteil.py (beide gemeinsam ändern).
// Basispunkte: 2000 = 20 %. betrag_cent bleibt der gezahlte Betrag; betrieblich ist der Rest.

export function privatCent(betragCent, bp) {
  return Math.floor((betragCent * bp + 5000) / 10000);
}

export function betrieblichCent(betragCent, bp) {
  return betragCent - privatCent(betragCent, bp);
}

// 2000 -> "20", 3333 -> "33,33"
export function bpZuText(bp) {
  if (!bp) return '';
  return (bp / 100).toFixed(2).replace(/0+$/, '').replace(/\.$/, '').replace('.', ',');
}

// "20" / "33,3" -> Basispunkte; leer oder ungültig (0 < x <= 100) -> null
export function textZuBp(text) {
  const t = String(text ?? '').trim().replace(',', '.');
  if (t === '') return null;
  const n = Number(t);
  if (!Number.isFinite(n) || n <= 0 || n > 100) return null;
  return Math.round(n * 100);
}
