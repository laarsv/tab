import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Spinner from './Spinner.jsx';

function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

// Beleg-Dateien (PDF/Bild) zu einer bestehenden Buchung. Nur im Edit-Modus sinnvoll.
export default function BelegeSection({ buchungId, onChange }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const inputRef = useRef(null);

  async function load() {
    try {
      const res = await api.get(`/api/buchungen/${buchungId}/belege`);
      setItems(res.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [buchungId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function upload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    setBusy(true);
    try {
      await api.post(`/api/buchungen/${buchungId}/belege`, form);
      toast.success('Beleg hochgeladen.');
      await load();
      onChange?.();
    } catch (err) {
      toast.error(apiError(err, 'Upload fehlgeschlagen.'));
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  async function open(beleg) {
    try {
      const res = await api.get(`/api/belege/${beleg.id}/download`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) {
      toast.error(apiError(e, 'Öffnen fehlgeschlagen.'));
    }
  }

  async function remove(beleg) {
    if (!window.confirm(`Beleg „${beleg.original_name}" löschen?`)) return;
    try {
      await api.delete(`/api/belege/${beleg.id}`);
      await load();
      onChange?.();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="label mb-0">Belege (PDF/JPG/PNG)</span>
        <button
          type="button"
          className="btn-outline btn-sm"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
        >
          {busy ? <Spinner size="sm" /> : '+ Datei'}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,image/jpeg,image/png"
          className="hidden"
          onChange={upload}
        />
      </div>

      {loading ? (
        <div className="text-sm text-ink/50">Lädt…</div>
      ) : items.length === 0 ? (
        <div className="rounded-lg bg-mint-soft/10 p-3 text-sm text-ink/60">
          Noch kein Beleg angehängt.
        </div>
      ) : (
        <ul className="divide-y divide-ink/5 rounded-lg border border-ink/10">
          {items.map((b) => (
            <li key={b.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
              <button
                type="button"
                onClick={() => open(b)}
                className="truncate text-left text-mint font-bold hover:underline"
                title={b.original_name}
              >
                {b.original_name}
              </button>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-ink/50 tabular-nums">{fileSize(b.size_bytes)}</span>
                <button
                  type="button"
                  onClick={() => remove(b)}
                  className="text-xs font-bold text-red-700 hover:underline"
                >
                  Löschen
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
