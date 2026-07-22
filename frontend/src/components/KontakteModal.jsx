import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Modal from './Modal.jsx';

function emptyForm() {
  return { name: '', anschrift: '', email: '', notiz: '' };
}

// Kontakte pflegen. Der Speicher füllt sich automatisch aus erstellten
// Rechnungen/Abos — hier nur ansehen, korrigieren, löschen, manuell ergänzen.
export default function KontakteModal({ gewerbeId, onClose, onChanged }) {
  const [items, setItems] = useState([]);
  const [form, setForm] = useState(null); // { id? , name, ... } | null
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const res = await api.get('/api/kontakte', { params: { gewerbe_id: gewerbeId } });
      setItems(res.data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(e) {
    e.preventDefault();
    if (!form.name.trim()) return toast.error('Name ist Pflicht.');
    const body = {
      name: form.name.trim(),
      anschrift: form.anschrift.trim() || null,
      email: form.email.trim() || null,
      notiz: form.notiz.trim() || null,
    };
    setBusy(true);
    try {
      if (form.id) {
        await api.patch(`/api/kontakte/${form.id}`, body);
      } else {
        await api.post('/api/kontakte', { gewerbe_id: Number(gewerbeId), ...body });
      }
      setForm(null);
      await load();
      onChanged?.();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(k) {
    if (!window.confirm(`Kontakt „${k.name}" löschen? Bestehende Rechnungen bleiben unverändert.`))
      return;
    try {
      await api.delete(`/api/kontakte/${k.id}`);
      await load();
      onChanged?.();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  return (
    <Modal title="Kontakte" onClose={onClose} maxWidth="max-w-2xl">
      <div className="space-y-4">
        <p className="text-sm text-ink/60">
          Füllt sich automatisch: Jede erstellte Rechnung merkt sich ihren Empfänger. In
          Rechnung und Abo dann einfach „Aus Kontakten übernehmen".
        </p>

        {items.length === 0 ? (
          <div className="card p-8 text-center text-ink/60 text-sm">
            Noch keine Kontakte — sie entstehen mit deiner ersten Rechnung.
          </div>
        ) : (
          <ul className="divide-y divide-ink/5 rounded-lg border border-ink/10">
            {items.map((k) => (
              <li key={k.id} className="flex items-start justify-between gap-3 px-3 py-2.5">
                <div className="min-w-0 text-sm">
                  <div className="font-bold truncate">{k.name}</div>
                  <div className="text-xs text-ink/60 truncate">
                    {[k.email, (k.anschrift || '').split('\n').join(', ')].filter(Boolean).join(' · ') || '—'}
                  </div>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button className="btn-ghost btn-sm" onClick={() => setForm({
                    id: k.id, name: k.name, anschrift: k.anschrift || '',
                    email: k.email || '', notiz: k.notiz || '',
                  })}>
                    Bearbeiten
                  </button>
                  <button className="btn-ghost btn-sm text-red-700" onClick={() => remove(k)}>
                    Löschen
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}

        {form ? (
          <form onSubmit={save} className="rounded-lg border border-ink/10 p-3 space-y-3">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
              <label className="block">
                <span className="field-label">Name/Firma</span>
                <input className="input" value={form.name} autoFocus
                  onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </label>
              <label className="block">
                <span className="field-label">E-Mail</span>
                <input className="input" value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </label>
            </div>
            <label className="block">
              <span className="field-label">Anschrift</span>
              <textarea className="input min-h-[56px]" value={form.anschrift}
                onChange={(e) => setForm({ ...form, anschrift: e.target.value })} />
            </label>
            <label className="block">
              <span className="field-label">Notiz (intern)</span>
              <input className="input" value={form.notiz}
                onChange={(e) => setForm({ ...form, notiz: e.target.value })} />
            </label>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-ghost btn-sm" onClick={() => setForm(null)}>
                Abbrechen
              </button>
              <button type="submit" className="btn-primary btn-sm" disabled={busy}>
                Speichern
              </button>
            </div>
          </form>
        ) : (
          <button className="btn-outline btn-sm" onClick={() => setForm(emptyForm())}>
            + Kontakt manuell anlegen
          </button>
        )}
      </div>
    </Modal>
  );
}
