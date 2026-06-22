import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Modal from '../components/Modal.jsx';
import { PageSpinner } from '../components/Spinner.jsx';

export default function Gewerbe() {
  const { reloadGewerbe, setGewerbeId } = useOutletContext();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // {id?, name, steuernummer}

  async function load() {
    setLoading(true);
    try {
      const res = await api.get('/api/gewerbe', { params: { include_inactive: true } });
      setItems(res.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(e) {
    e.preventDefault();
    const body = {
      name: editing.name?.trim(),
      steuernummer: editing.steuernummer?.trim() || null,
      besteuerung: editing.besteuerung || 'kleinunternehmer',
    };
    if (!body.name) return toast.error('Name ist Pflicht.');
    try {
      if (editing.id) {
        await api.patch(`/api/gewerbe/${editing.id}`, body);
        toast.success('Gespeichert.');
      } else {
        const res = await api.post('/api/gewerbe', body);
        toast.success('Gewerbe angelegt.');
        setGewerbeId(String(res.data.id));
      }
      setEditing(null);
      await load();
      await reloadGewerbe();
    } catch (err) {
      toast.error(apiError(err));
    }
  }

  async function toggleAktiv(g) {
    try {
      await api.patch(`/api/gewerbe/${g.id}`, { aktiv: !g.aktiv });
      await load();
      await reloadGewerbe();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Gewerbe</h1>
          <p className="text-xs text-ink/60 mt-0.5">Eine EÜR pro Gewerbe. Deaktivieren statt löschen.</p>
        </div>
        <button
          className="btn-primary w-full sm:w-auto"
          onClick={() => setEditing({ name: '', steuernummer: '', besteuerung: 'kleinunternehmer' })}
        >
          + Gewerbe
        </button>
      </div>

      {items.length === 0 ? (
        <div className="card p-12 text-center text-ink/60">
          Noch kein Gewerbe angelegt. Lege dein erstes Gewerbe an (z. B. „Makler" oder „App").
        </div>
      ) : (
        <div className="card divide-y divide-ink/5">
          {items.map((g) => (
            <div key={g.id} className="flex items-center justify-between gap-3 p-4">
              <div className="min-w-0">
                <div className="font-bold flex items-center gap-2">
                  <span className="truncate">{g.name}</span>
                  {!g.aktiv && (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-mint-soft/40 text-ink text-[10px] font-bold uppercase tracking-wider">
                      inaktiv
                    </span>
                  )}
                  {g.besteuerung === 'regelbesteuerung' ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-900 text-[10px] font-bold uppercase tracking-wider">
                      Regelbest.
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-mint-soft/40 text-ink text-[10px] font-bold uppercase tracking-wider">
                      §19 KU
                    </span>
                  )}
                </div>
                <div className="text-xs text-ink/60 mt-0.5">
                  {g.steuernummer ? `St.-Nr. ${g.steuernummer}` : 'keine Steuernummer'}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <button
                  className="btn-outline btn-sm"
                  onClick={() =>
                    setEditing({
                      id: g.id,
                      name: g.name,
                      steuernummer: g.steuernummer || '',
                      besteuerung: g.besteuerung || 'kleinunternehmer',
                    })
                  }
                >
                  Bearbeiten
                </button>
                <button className="btn-ghost btn-sm" onClick={() => toggleAktiv(g)}>
                  {g.aktiv ? 'Deaktivieren' : 'Aktivieren'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && (
        <Modal
          title={editing.id ? 'Gewerbe bearbeiten' : 'Neues Gewerbe'}
          onClose={() => setEditing(null)}
        >
          <form onSubmit={save} className="space-y-4">
            <label className="block">
              <span className="label">Name</span>
              <input
                className="input"
                value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                autoFocus
              />
            </label>
            <label className="block">
              <span className="label">Steuernummer (optional)</span>
              <input
                className="input"
                value={editing.steuernummer}
                onChange={(e) => setEditing({ ...editing, steuernummer: e.target.value })}
              />
            </label>

            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5 rounded border-ink/30 text-mint focus:ring-mint"
                checked={(editing.besteuerung || 'kleinunternehmer') === 'kleinunternehmer'}
                onChange={(e) =>
                  setEditing({
                    ...editing,
                    besteuerung: e.target.checked ? 'kleinunternehmer' : 'regelbesteuerung',
                  })
                }
              />
              <span>
                <span className="font-bold">Kleinunternehmer §19 UStG</span>
                <span className="block text-xs text-ink/60">
                  Aktiv = alles brutto, EÜR-Export verfügbar. Deaktiviert (Regelbesteuerung) wird
                  der Export noch nicht unterstützt.
                </span>
              </span>
            </label>

            <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
              <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>
                Abbrechen
              </button>
              <button type="submit" className="btn-primary">
                Speichern
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
