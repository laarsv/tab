import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';

// Beleg (auth-geschützt) als Blob holen und in neuem Tab öffnen.
export async function openBeleg(id) {
  try {
    const res = await api.get(`/api/belege/${id}/download`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    toast.error(apiError(e, 'Öffnen fehlgeschlagen.'));
  }
}

export function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export const ACCEPT = 'application/pdf,image/jpeg,image/png,application/xml,text/xml,.xml';

// Dateityp eines Belegs bestimmen (für Icon/Vorschau): 'pdf' | 'bild' | 'xml' | 'sonst'.
export function belegTyp(beleg) {
  const ct = (beleg?.content_type || '').toLowerCase();
  const name = (beleg?.original_name || '').toLowerCase();
  if (ct.includes('pdf') || name.endsWith('.pdf')) return 'pdf';
  if (ct.startsWith('image/') || /\.(jpe?g|png)$/.test(name)) return 'bild';
  if (ct.includes('xml') || name.endsWith('.xml')) return 'xml';
  return 'sonst';
}

export const TYP_LABEL = { pdf: 'PDF', bild: 'Bild', xml: 'XML', sonst: 'Datei' };

// Inline-URL (Anzeige im Browser statt Download) — same-origin, Session-Cookie wird
// automatisch mitgeschickt.
export function belegInlineUrl(id) {
  const base = import.meta.env.VITE_API_BASE_URL || '';
  return `${base}/api/belege/${id}/download?inline=1`;
}
