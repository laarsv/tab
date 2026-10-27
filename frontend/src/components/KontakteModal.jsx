import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { DialogFuss } from './DialogParts.jsx';
import { IconButton, IconPencil, IconPlus, IconTrash, IconUsers } from './Icons.jsx';
import Modal from './Modal.jsx';
import { Row } from './PageParts.jsx';

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
    <Modal
      title="Kontakte"
      subtitle={'Füllt sich automatisch: Jede erstellte Rechnung merkt sich ihren Empfänger. In Rechnung und Abo dann einfach „Aus Kontakten übernehmen“.'}
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <div className="space-y-4">
        <div className="border-t border-ink/[0.08]">
          {items.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink/60">
              Noch keine Kontakte — sie entstehen mit deiner ersten Rechnung.
            </p>
          ) : (
            items.map((k) => (
              <Row
                key={k.id}
                icon={IconUsers}
                title={k.name}
                sub={
                  <span className="truncate">
                    {[k.email, (k.anschrift || '').split('\n').join(', ')].filter(Boolean).join(' · ') || '—'}
                  </span>
                }
                actions={
                  <>
                    <IconButton
                      icon={IconPencil}
                      label="Bearbeiten"
                      onClick={() =>
                        setForm({
                          id: k.id,
                          name: k.name,
                          anschrift: k.anschrift || '',
                          email: k.email || '',
                          notiz: k.notiz || '',
                        })
                      }
                    />
                    <IconButton icon={IconTrash} variant="danger" label="Kontakt löschen" onClick={() => remove(k)} />
                  </>
                }
              />
            ))
          )}
        </div>

        {form ? (
          <form onSubmit={save} className="space-y-3 rounded-xl bg-surface p-4">
            <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
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
          <DialogFuss links={
            <button className="btn-ghost btn-sm" onClick={() => setForm(emptyForm())}>
              <IconPlus className="mr-1 h-3.5 w-3.5" /> Kontakt manuell anlegen
            </button>
          }>
            <button className="btn-primary" onClick={onClose}>
              Fertig
            </button>
          </DialogFuss>
        )}
      </div>
    </Modal>
  );
}
