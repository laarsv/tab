import { useEffect, useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Spinner from './Spinner.jsx';
import { openBeleg, fileSize, ACCEPT } from '../lib/belege.js';

// Belege einer bestehenden Buchung: anzeigen, öffnen, hochladen, aus Eingang anhängen, entfernen.
export default function BelegeManager({ buchungId, gewerbeId, onChange }) {
  const [attached, setAttached] = useState([]);
  const [inbox, setInbox] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [showInbox, setShowInbox] = useState(false);
  const inputRef = useRef(null);

  async function load() {
    try {
      const [att, ofn] = await Promise.all([
        api.get(`/api/buchungen/${buchungId}/belege`),
        api.get('/api/belege', { params: { gewerbe_id: gewerbeId, status: 'offen' } }),
      ]);
      setAttached(att.data);
      setInbox(ofn.data);
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
    form.append('gewerbe_id', gewerbeId);
    form.append('buchung_id', buchungId);
    setBusy(true);
    try {
      await api.post('/api/belege', form);
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

  async function attach(beleg) {
    try {
      await api.patch(`/api/belege/${beleg.id}`, { buchung_id: buchungId });
      await load();
      onChange?.();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function detach(beleg) {
    try {
      await api.patch(`/api/belege/${beleg.id}`, { buchung_id: null });
      await load();
      onChange?.();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (loading) return <div className="text-sm text-ink/50">Lädt…</div>;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span className="label mb-0">Belege</span>
        <div className="flex items-center gap-2">
          {inbox.length > 0 && (
            <button type="button" className="btn-ghost btn-sm" onClick={() => setShowInbox((s) => !s)}>
              Aus Eingang ({inbox.length})
            </button>
          )}
          <button
            type="button"
            className="btn-outline btn-sm"
            onClick={() => inputRef.current?.click()}
            disabled={busy}
          >
            {busy ? <Spinner size="sm" /> : '+ Datei'}
          </button>
          <input ref={inputRef} type="file" accept={ACCEPT} className="hidden" onChange={upload} />
        </div>
      </div>

      {showInbox && inbox.length > 0 && (
        <ul className="rounded-lg border border-ink/10 divide-y divide-ink/5">
          {inbox.map((b) => (
            <li key={b.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
              <span className="truncate">{b.original_name}</span>
              <button type="button" className="text-mint font-bold text-xs hover:underline" onClick={() => attach(b)}>
                Anhängen
              </button>
            </li>
          ))}
        </ul>
      )}

      {attached.length === 0 ? (
        <div className="rounded-lg bg-mint-soft/10 p-3 text-sm text-ink/60">Kein Beleg angehängt.</div>
      ) : (
        <ul className="divide-y divide-ink/5 rounded-lg border border-ink/10">
          {attached.map((b) => (
            <li key={b.id} className="flex items-center justify-between gap-2 px-3 py-2 text-sm">
              <button
                type="button"
                onClick={() => openBeleg(b.id)}
                className="truncate text-left text-mint font-bold hover:underline"
                title={b.original_name}
              >
                {b.original_name}
              </button>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-ink/50 tabular-nums">{fileSize(b.size_bytes)}</span>
                <button
                  type="button"
                  onClick={() => detach(b)}
                  className="text-xs font-bold text-ink/60 hover:underline"
                  title="Zurück in den Eingang"
                >
                  Entfernen
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
