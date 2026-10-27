import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { IconBriefcase, IconButton, IconPause, IconPencil, IconPlay, IconPlus } from '../components/Icons.jsx';
import { DialogFuss, SchalterZeile } from '../components/DialogParts.jsx';
import Modal from '../components/Modal.jsx';
import { Leer, PageHeader, PUNKT, Row, Zustand } from '../components/PageParts.jsx';
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
      anschrift: editing.anschrift?.trim() || null,
      iban: editing.iban?.trim() || null,
      rechnung_fusszeile: editing.rechnung_fusszeile?.trim() || null,
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

  function neu() {
    setEditing({
      name: '',
      steuernummer: '',
      besteuerung: 'kleinunternehmer',
      anschrift: '',
      iban: '',
      rechnung_fusszeile: '',
    });
  }

  return (
    <div>
      <PageHeader title="Gewerbe" sub="Eine EÜR pro Gewerbe. Deaktivieren statt löschen.">
        <button className="btn-primary" onClick={neu}>
          <IconPlus className="mr-1 h-4 w-4" /> Gewerbe
        </button>
      </PageHeader>

      <div className="mt-6">
        {items.length === 0 ? (
          <Leer>Noch kein Gewerbe angelegt. Lege dein erstes Gewerbe an (z. B. „Makler" oder „App").</Leer>
        ) : (
          items.map((g) => (
            <Row
              key={g.id}
              icon={IconBriefcase}
              title={g.name}
              muted={!g.aktiv}
              sub={
                <>
                  {g.besteuerung === 'regelbesteuerung' ? (
                    <Zustand ton="warn">Regelbesteuerung</Zustand>
                  ) : (
                    <span>Kleinunternehmer §19</span>
                  )}
                  {PUNKT}
                  <span>{g.steuernummer ? `St.-Nr. ${g.steuernummer}` : 'keine Steuernummer'}</span>
                  {!g.aktiv && (
                    <>
                      {PUNKT}
                      <span className="font-bold">inaktiv</span>
                    </>
                  )}
                </>
              }
              actions={
                <>
                  <IconButton
                    icon={IconPencil}
                    label="Bearbeiten"
                    onClick={() =>
                      setEditing({
                        id: g.id,
                        name: g.name,
                        steuernummer: g.steuernummer || '',
                        besteuerung: g.besteuerung || 'kleinunternehmer',
                        anschrift: g.anschrift || '',
                        iban: g.iban || '',
                        rechnung_fusszeile: g.rechnung_fusszeile || '',
                      })
                    }
                  />
                  <IconButton
                    icon={g.aktiv ? IconPause : IconPlay}
                    label={g.aktiv ? 'Deaktivieren' : 'Aktivieren'}
                    onClick={() => toggleAktiv(g)}
                  />
                </>
              }
            />
          ))
        )}
      </div>

      {editing && (
        <Modal
          title={editing.id ? 'Gewerbe bearbeiten' : 'Neues Gewerbe'}
          onClose={() => setEditing(null)}
        >
          <form onSubmit={save} className="space-y-4">
            <label className="block">
              <span className="field-label">Name</span>
              <input
                className="input"
                value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                autoFocus
              />
            </label>
            <label className="block">
              <span className="field-label">Steuernummer (optional)</span>
              <input
                className="input"
                value={editing.steuernummer}
                onChange={(e) => setEditing({ ...editing, steuernummer: e.target.value })}
              />
            </label>

            <label className="block">
              <span className="field-label">Rechnungs-Absender: Name & Anschrift</span>
              <textarea
                className="input min-h-[80px]"
                value={editing.anschrift}
                onChange={(e) => setEditing({ ...editing, anschrift: e.target.value })}
                placeholder={'Max Mustermann\nMusterstraße 1\n20095 Hamburg'}
              />
              <span className="block text-xs text-ink/60 mt-1">
                Erscheint auf Rechnungen (Pflichtangabe).
              </span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
              <label className="block">
                <span className="field-label">IBAN (für Rechnungen)</span>
                <input
                  className="input"
                  value={editing.iban}
                  onChange={(e) => setEditing({ ...editing, iban: e.target.value })}
                  placeholder="DE12 3456 …"
                />
              </label>
              <label className="block">
                <span className="field-label">Rechnungs-Fußzeile (optional)</span>
                <input
                  className="input"
                  value={editing.rechnung_fusszeile}
                  onChange={(e) => setEditing({ ...editing, rechnung_fusszeile: e.target.value })}
                  placeholder="z. B. Bank, Zahlungsziel 14 Tage"
                />
              </label>
            </div>

            <SchalterZeile
              titel="Kleinunternehmer §19 UStG"
              hinweis="An = alles brutto, EÜR-Export verfügbar. Aus (Regelbesteuerung) wird der Export noch nicht unterstützt."
              checked={(editing.besteuerung || 'kleinunternehmer') === 'kleinunternehmer'}
              onChange={(an) =>
                setEditing({ ...editing, besteuerung: an ? 'kleinunternehmer' : 'regelbesteuerung' })
              }
            />

            <DialogFuss>
              <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>
                Abbrechen
              </button>
              <button type="submit" className="btn-primary">
                Speichern
              </button>
            </DialogFuss>
          </form>
        </Modal>
      )}
    </div>
  );
}
