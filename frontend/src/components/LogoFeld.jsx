import { useRef, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';

// Firmenlogo (PNG/JPG) für Rechnung, Mahnung und Angebot. Das Bild kommt mit dem Login-Cookie vom
// Server; `version` zwingt den Browser nach Upload/Entfernen zum Neuladen.
export default function LogoFeld({ gewerbeId, hatLogo, onChanged }) {
  const inputRef = useRef(null);
  const [version, setVersion] = useState(() => Date.now());
  const [busy, setBusy] = useState(false);

  async function hochladen(file) {
    if (!file) return;
    const form = new FormData();
    form.append('file', file);
    setBusy(true);
    try {
      const res = await api.post(`/api/gewerbe/${gewerbeId}/logo`, form);
      setVersion(Date.now());
      onChanged(res.data);
      toast.success('Logo gespeichert.');
    } catch (e) {
      toast.error(apiError(e, 'Logo konnte nicht gespeichert werden.'));
    } finally {
      setBusy(false);
    }
  }

  async function entfernen() {
    setBusy(true);
    try {
      const res = await api.delete(`/api/gewerbe/${gewerbeId}/logo`);
      setVersion(Date.now());
      onChanged(res.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-4">
      <div className="flex h-16 w-40 shrink-0 items-center justify-center rounded-xl bg-surface p-2">
        {hatLogo ? (
          <img
            src={`${api.defaults.baseURL || ''}/api/gewerbe/${gewerbeId}/logo?v=${version}`}
            alt="Firmenlogo"
            className="max-h-full max-w-full object-contain"
          />
        ) : (
          <span className="text-xs text-ink/60">Kein Logo</span>
        )}
      </div>
      <div className="min-w-0 flex-1 space-y-1">
        <div className="flex flex-wrap gap-2">
          <button type="button" className="btn-outline btn-sm" disabled={busy} onClick={() => inputRef.current?.click()}>
            {hatLogo ? 'Ersetzen' : 'Logo hochladen'}
          </button>
          {hatLogo && (
            <button type="button" className="btn-ghost btn-sm" disabled={busy} onClick={entfernen}>
              Entfernen
            </button>
          )}
        </div>
        <p className="text-xs text-ink/60">
          PNG oder JPG, am besten quer und mit transparentem Hintergrund. Steht oben rechts auf Rechnung, Mahnung und
          Angebot.
        </p>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept="image/png,image/jpeg"
        className="hidden"
        onChange={(e) => {
          hochladen(e.target.files?.[0]);
          e.target.value = '';
        }}
      />
    </div>
  );
}
