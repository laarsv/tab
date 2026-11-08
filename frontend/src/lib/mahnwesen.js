import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { tageZwischen } from './fristen.js';

// Mahnstufen — Spiegel von backend/app/services/mahnwesen.py (Texte und Rechenregeln dort).
export const STUFEN = { 1: 'Zahlungserinnerung', 2: '1. Mahnung', 3: 'Letzte Mahnung' };
export const PAUSCHALE_CENT = 40_00; // § 288 Abs. 5 BGB, nur gegenüber Geschäftskunden

export function naechsteStufe(letzteMahnung) {
  return Math.min((letzteMahnung?.stufe ?? 0) + 1, 3);
}

// Verzugszinsen: Betrag x Satz x Tage / 365, kaufmännisch gerundet (Satz in Basispunkten).
export function verzugszinsenCent(offen, satzBp, tage) {
  if (offen <= 0 || satzBp <= 0 || tage <= 0) return 0;
  const nenner = 10_000 * 365;
  return Math.floor((2 * offen * satzBp * tage + nenner) / (2 * nenner));
}

// Forderungsaufstellung für die Live-Anzeige. Maßgeblich ist, was der Server beim Erstellen
// rechnet — hier dieselbe Formel. Die Pauschale wird auf eine Mahngebühr angerechnet (§ 288 Abs. 5 S. 3).
export function mahnbetraege({ offen, faellig, datum, gebuehr, pauschale, satzBp }) {
  const zinstage = satzBp === null ? 0 : Math.max(0, tageZwischen(faellig, datum));
  const zinsen = satzBp === null ? 0 : verzugszinsenCent(offen, satzBp, zinstage);
  const pauschaleCent = pauschale ? PAUSCHALE_CENT : 0;
  const gebuehrCent = Math.max(0, gebuehr - pauschaleCent);
  return {
    offen,
    gebuehr: gebuehrCent,
    pauschale: pauschaleCent,
    zinsen,
    zinssatzBp: satzBp ?? 0,
    zinstage,
    gesamt: offen + gebuehrCent + pauschaleCent + zinsen,
  };
}

export function formatProzent(bp) {
  return `${(bp / 100).toLocaleString('de-DE', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} %`;
}

export async function openMahnungPdf(id) {
  try {
    const res = await api.get(`/api/mahnwesen/${id}/pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    toast.error(apiError(e, 'PDF konnte nicht erstellt werden.'));
  }
}
