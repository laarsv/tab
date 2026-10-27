import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Dropdown from '../components/Dropdown.jsx';
import { IconButton, IconPencil, IconPlus, IconTrash, IconTrendDown } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import { Hinweis, KeinGewerbe, Kennzahl, Kennzahlen, Leer, PageHeader, PUNKT, Row } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro, formatDateDE, parseEuroToCent, centToInput, todayISO } from '../lib/format.js';

export default function Afa() {
  const { gewerbeId, jahr } = useOutletContext();
  const [afaKategorien, setAfaKategorien] = useState([]);
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [kat, afa] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr } }),
        api.get('/api/afa', { params: { gewerbe_id: gewerbeId, jahr } }),
      ]);
      setAfaKategorien(kat.data.filter((k) => k.ist_afa));
      setItems(afa.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  const sumJahresAfa = useMemo(
    () => items.reduce((s, a) => s + (a.jahres_afa_cent || 0), 0),
    [items],
  );

  async function remove(id) {
    if (!window.confirm('Dieses Wirtschaftsgut wirklich löschen?')) return;
    try {
      await api.delete(`/api/afa/${id}`);
      toast.success('Gelöscht.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  function openNew() {
    const def = afaKategorien[0];
    setEditing({
      kategorie_id: def ? String(def.id) : '',
      bezeichnung: '',
      kostenInput: '',
      anschaffungsdatum: todayISO(),
      nutzungsdauer_jahre: 3,
      sofort: false,
      abgang: false,
      abgang_datum: '',
      beschreibung: '',
    });
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div>
      <PageHeader
        title="Abschreibungen (AfA)"
        sub={`Teure Anschaffungen über mehrere Jahre absetzen · Jahres-AfA ${jahr} fließt in Zeile 33.`}
      >
        <button className="btn-primary" onClick={openNew}>
          <IconPlus className="mr-1 h-4 w-4" /> Anschaffung
        </button>
      </PageHeader>

      <Hinweis titel="Wann gehört etwas hierher?" className="mt-5 space-y-1">
        <p>
          Kostet eine Anschaffung <strong>mehr als 800 € netto</strong> (≈ 952 € brutto), darfst du sie nicht auf
          einmal absetzen, sondern verteilst sie über die Nutzungsdauer — die Jahresrate heißt{' '}
          <strong>Abschreibung (AfA)</strong>. Du legst die Anschaffung hier einmal an, Tab rechnet die
          Jahresbeträge automatisch und nimmt sie in jeden Export mit.
        </p>
        <p>
          <strong>Ausnahme:</strong> Computer, Laptop &amp; Software dürfen mit Nutzungsdauer 1 Jahr sofort komplett
          abgesetzt werden — dafür gibt's den Haken „Sofortabzug". Günstigeres (≤ 800 € netto) buchst du einfach
          als <strong>GWG</strong> direkt bei den Buchungen. Verkauft oder ausgemustert? Beim Bearbeiten das
          Abgangsdatum setzen.
        </p>
      </Hinweis>

      <Kennzahlen cols={1} className="mt-6">
        <Kennzahl label={`Summe Jahres-AfA ${jahr} (Zeile 33)`} value={formatEuro(sumJahresAfa)} />
      </Kennzahlen>

      <div className="mt-2">
        {items.length === 0 ? (
          <Leer>Noch keine Anschaffungen erfasst. Nur nötig für Käufe über 800 € netto.</Leer>
        ) : (
          items.map((a) => (
            <Row
              key={a.id}
              icon={IconTrendDown}
              title={a.bezeichnung}
              sub={
                <>
                  <span className="tabular-nums">{formatDateDE(a.anschaffungsdatum)}</span>
                  {PUNKT}
                  <span className="tabular-nums">{formatEuro(a.anschaffungskosten_cent)}</span>
                  {PUNKT}
                  <span>{a.nutzungsdauer_jahre === 1 ? 'Sofortabzug' : `${a.nutzungsdauer_jahre} Jahre`}</span>
                  {a.abgang_datum && (
                    <>
                      {PUNKT}
                      <span>
                        Abgang {formatDateDE(a.abgang_datum)}
                        {a.restbuchwert_cent > 0 && (
                          <> · Restbuchwert {formatEuro(a.restbuchwert_cent)} → als Buchung Zeile 38 erfassen</>
                        )}
                      </span>
                    </>
                  )}
                </>
              }
              amount={formatEuro(a.jahres_afa_cent || 0)}
              actions={
                <>
                  <IconButton icon={IconPencil} label="Bearbeiten" onClick={() => setEditing(toEdit(a))} />
                  <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => remove(a.id)} />
                </>
              }
            />
          ))
        )}
      </div>

      {editing && (
        <AfaModal
          editing={editing}
          setEditing={setEditing}
          afaKategorien={afaKategorien}
          gewerbeId={gewerbeId}
          onSaved={load}
        />
      )}
    </div>
  );
}

function toEdit(a) {
  return {
    id: a.id,
    kategorie_id: String(a.kategorie_id),
    bezeichnung: a.bezeichnung,
    kostenInput: centToInput(a.anschaffungskosten_cent),
    anschaffungsdatum: a.anschaffungsdatum,
    nutzungsdauer_jahre: a.nutzungsdauer_jahre,
    sofort: a.nutzungsdauer_jahre === 1,
    abgang: Boolean(a.abgang_datum),
    abgang_datum: a.abgang_datum || '',
    beschreibung: a.beschreibung || '',
  };
}

function AfaModal({ editing, setEditing, afaKategorien, gewerbeId, onSaved }) {
  const [busy, setBusy] = useState(false);
  const options = afaKategorien.map((k) => ({
    value: String(k.id),
    label: k.euer_zeile ? `${k.name} · Zeile ${k.euer_zeile}` : k.name,
  }));

  async function save(e) {
    e.preventDefault();
    const kosten = parseEuroToCent(editing.kostenInput);
    if (!editing.bezeichnung.trim()) return toast.error('Bezeichnung ist Pflicht.');
    if (!editing.kategorie_id) return toast.error('Bitte AfA-Kategorie wählen.');
    if (!kosten || kosten <= 0) return toast.error('Bitte gültige Anschaffungskosten eingeben.');
    const nd = editing.sofort ? 1 : Number(editing.nutzungsdauer_jahre);
    if (!nd || nd < 1) return toast.error('Nutzungsdauer muss mindestens 1 Jahr sein.');

    if (editing.abgang && !editing.abgang_datum) return toast.error('Bitte Abgangsdatum angeben.');

    const body = {
      gewerbe_id: Number(gewerbeId),
      kategorie_id: Number(editing.kategorie_id),
      bezeichnung: editing.bezeichnung.trim(),
      anschaffungskosten_cent: kosten,
      anschaffungsdatum: editing.anschaffungsdatum,
      nutzungsdauer_jahre: nd,
      abgang_datum: editing.abgang ? editing.abgang_datum : null,
      beschreibung: editing.beschreibung.trim() || null,
    };
    setBusy(true);
    try {
      if (editing.id) {
        await api.patch(`/api/afa/${editing.id}`, body);
        toast.success('Gespeichert.');
      } else {
        await api.post('/api/afa', body);
        toast.success('Wirtschaftsgut angelegt.');
      }
      setEditing(null);
      await onSaved();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={editing.id ? 'Anschaffung bearbeiten' : 'Neue Anschaffung (AfA)'}
      onClose={() => setEditing(null)}
    >
      <form onSubmit={save} className="space-y-4">
        <label className="block">
          <span className="field-label">Bezeichnung</span>
          <input
            className="input"
            value={editing.bezeichnung}
            onChange={(e) => setEditing({ ...editing, bezeichnung: e.target.value })}
            placeholder="z. B. MacBook Pro"
            autoFocus
          />
        </label>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
          <label className="block">
            <span className="field-label">Anschaffungskosten brutto (€)</span>
            <input
              className="input tabular-nums"
              inputMode="decimal"
              value={editing.kostenInput}
              onChange={(e) => setEditing({ ...editing, kostenInput: e.target.value })}
              placeholder="0,00"
            />
          </label>
          <label className="block">
            <span className="field-label">Anschaffungsdatum</span>
            <input
              type="date"
              className="input"
              value={editing.anschaffungsdatum}
              onChange={(e) => setEditing({ ...editing, anschaffungsdatum: e.target.value })}
            />
          </label>
        </div>

        {afaKategorien.length > 1 && (
          <div className="block">
            <span className="field-label">Kategorie</span>
            <Dropdown
              value={editing.kategorie_id}
              onChange={(v) => setEditing({ ...editing, kategorie_id: String(v) })}
              options={options}
              searchable
            />
          </div>
        )}

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="rounded border-ink/30 text-royal focus:ring-royal"
            checked={editing.sofort}
            onChange={(e) => setEditing({ ...editing, sofort: e.target.checked })}
          />
          <span>Sofortabzug (Nutzungsdauer 1 Jahr) — Computer-Hardware / Software</span>
        </label>

        {!editing.sofort && (
          <label className="block">
            <span className="field-label">Nutzungsdauer (Jahre)</span>
            <input
              type="number"
              min="1"
              max="50"
              className="input tabular-nums"
              value={editing.nutzungsdauer_jahre}
              onChange={(e) => setEditing({ ...editing, nutzungsdauer_jahre: e.target.value })}
            />
            <span className="block text-xs text-ink/60 mt-1">
              Linear, monatsgenau ab Anschaffungsmonat.
            </span>
          </label>
        )}

        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="rounded border-ink/30 text-royal focus:ring-royal"
              checked={editing.abgang}
              onChange={(e) => setEditing({ ...editing, abgang: e.target.checked })}
            />
            <span>Abgang (Verkauf / Entnahme / Verschrottung)</span>
          </label>
          {editing.abgang && (
            <>
              <label className="block">
                <span className="field-label">Abgangsdatum</span>
                <input
                  type="date"
                  className="input"
                  value={editing.abgang_datum}
                  onChange={(e) => setEditing({ ...editing, abgang_datum: e.target.value })}
                />
              </label>
              <div className="rounded-lg bg-royal-soft/15 border-l-4 border-royal-soft p-2.5 text-xs text-ink/80">
                Die AfA endet mit dem Abgangsmonat. Den Restbuchwert (wird in der Liste angezeigt)
                als Buchung „Restbuchwert" (Zeile 38) erfassen, einen Verkaufserlös als
                „Veräußerung Anlagevermögen" (Zeile 19).
              </div>
            </>
          )}
        </div>

        <label className="block">
          <span className="field-label">Notiz (optional)</span>
          <input
            className="input"
            value={editing.beschreibung}
            onChange={(e) => setEditing({ ...editing, beschreibung: e.target.value })}
          />
        </label>

        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
          <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            Speichern
          </button>
        </div>
      </form>
    </Modal>
  );
}
