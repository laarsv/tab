import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { DialogFuss } from './DialogParts.jsx';
import { IconBookmark, IconButton, IconFileText, IconPencil, IconPlus, IconTrash } from './Icons.jsx';
import Modal from './Modal.jsx';
import { Row } from './PageParts.jsx';
import { centToInput, formatEuro, parseEuroToCent } from '../lib/format.js';

// Artikelkatalog (Bezeichnung + Preis) und Textbausteine (Name + Text) pflegen.
export default function VorlagenModal({ gewerbeId, onClose }) {
  const [tab, setTab] = useState('artikel');
  const [artikel, setArtikel] = useState([]);
  const [bausteine, setBausteine] = useState([]);
  const [form, setForm] = useState(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      const [a, b] = await Promise.all([
        api.get('/api/artikel', { params: { gewerbe_id: gewerbeId } }),
        api.get('/api/textbausteine', { params: { gewerbe_id: gewerbeId } }),
      ]);
      setArtikel(a.data);
      setBausteine(b.data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }
  useEffect(() => {
    load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const istArtikel = tab === 'artikel';
  const pfad = istArtikel ? '/api/artikel' : '/api/textbausteine';

  async function save(e) {
    e.preventDefault();
    let body;
    if (istArtikel) {
      const preis = parseEuroToCent(form.preis);
      if (!form.name.trim()) return toast.error('Bezeichnung ist Pflicht.');
      if (!preis || preis <= 0) return toast.error('Bitte einen Preis über 0 € angeben.');
      body = { bezeichnung: form.name.trim(), preis_cent: preis };
    } else {
      if (!form.name.trim() || !form.text.trim()) return toast.error('Name und Text sind Pflicht.');
      body = { name: form.name.trim(), text: form.text.trim() };
    }
    setBusy(true);
    try {
      if (form.id) await api.patch(`${pfad}/${form.id}`, body);
      else await api.post(pfad, { gewerbe_id: Number(gewerbeId), ...body });
      setForm(null);
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(item) {
    const name = item.bezeichnung || item.name;
    if (!window.confirm(`„${name}" löschen? Bestehende Rechnungen und Angebote bleiben unverändert.`)) return;
    try {
      await api.delete(`${pfad}/${item.id}`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  const liste = istArtikel ? artikel : bausteine;

  return (
    <Modal
      title="Artikel & Texte"
      subtitle="Häufige Positionen und Textbausteine einmal anlegen, im Rechnungs- und Angebotsfenster per Auswahl einfügen."
      onClose={onClose}
      maxWidth="max-w-2xl"
    >
      <div className="space-y-4">
        <div className="flex gap-2">
          {[
            ['artikel', 'Artikel'],
            ['texte', 'Textbausteine'],
          ].map(([k, label]) => (
            <button
              key={k}
              type="button"
              className={`${tab === k ? 'btn-primary' : 'btn-outline'} btn-sm`}
              onClick={() => {
                setTab(k);
                setForm(null);
              }}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="border-t border-ink/[0.08]">
          {liste.length === 0 ? (
            <p className="py-8 text-center text-sm text-ink/60">
              {istArtikel
                ? 'Noch keine Artikel — z. B. Stundensatz oder Pauschale. Oder im Rechnungsfenster eine Position mit dem Lesezeichen speichern.'
                : 'Noch keine Textbausteine — z. B. ein Dank zum Schluss oder Zahlungsbedingungen.'}
            </p>
          ) : (
            liste.map((it) => (
              <Row
                key={it.id}
                icon={istArtikel ? IconBookmark : IconFileText}
                title={istArtikel ? it.bezeichnung : it.name}
                sub={istArtikel ? undefined : <span className="truncate">{it.text.split('\n')[0]}</span>}
                amount={istArtikel ? formatEuro(it.preis_cent) : undefined}
                actions={
                  <>
                    <IconButton
                      icon={IconPencil}
                      label="Bearbeiten"
                      onClick={() =>
                        setForm(
                          istArtikel
                            ? { id: it.id, name: it.bezeichnung, preis: centToInput(it.preis_cent) }
                            : { id: it.id, name: it.name, text: it.text },
                        )
                      }
                    />
                    <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => remove(it)} />
                  </>
                }
              />
            ))
          )}
        </div>

        {form ? (
          <form onSubmit={save} className="space-y-3 rounded-xl bg-surface p-4">
            <div className={istArtikel ? 'grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-3' : ''}>
              <label className={`block ${istArtikel ? 'sm:col-span-2' : ''}`}>
                <span className="field-label">{istArtikel ? 'Bezeichnung' : 'Name'}</span>
                <input className="input" value={form.name} autoFocus maxLength={istArtikel ? 500 : 80}
                  placeholder={istArtikel ? 'z. B. Stundensatz Beratung' : 'z. B. Dank zum Schluss'}
                  onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </label>
              {istArtikel && (
                <label className="block">
                  <span className="field-label">Preis (€)</span>
                  <input className="input tabular-nums" inputMode="decimal" placeholder="0,00" value={form.preis}
                    onChange={(e) => setForm({ ...form, preis: e.target.value })} />
                </label>
              )}
            </div>
            {!istArtikel && (
              <label className="block">
                <span className="field-label">Text</span>
                <textarea className="input min-h-[96px]" maxLength={2000} value={form.text}
                  onChange={(e) => setForm({ ...form, text: e.target.value })} />
              </label>
            )}
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
          <DialogFuss
            links={
              <button
                className="btn-ghost btn-sm"
                onClick={() => setForm(istArtikel ? { name: '', preis: '' } : { name: '', text: '' })}
              >
                <IconPlus className="mr-1 h-3.5 w-3.5" /> {istArtikel ? 'Artikel anlegen' : 'Textbaustein anlegen'}
              </button>
            }
          >
            <button className="btn-primary" onClick={onClose}>
              Fertig
            </button>
          </DialogFuss>
        )}
      </div>
    </Modal>
  );
}
