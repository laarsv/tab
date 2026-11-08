import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Dropdown from '../components/Dropdown.jsx';
import { IconButton, IconPencil, IconPlus, IconTrash, IconTrendDown } from '../components/Icons.jsx';
import { DialogFuss, Gruppe, SchalterZeile } from '../components/DialogParts.jsx';
import Modal from '../components/Modal.jsx';
import AbschlussHinweis from '../components/AbschlussHinweis.jsx';
import { Hinweis, KeinGewerbe, Kennzahl, Kennzahlen, Leer, PageHeader, PUNKT, Row } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro, formatDateDE, parseEuroToCent, centToInput, todayISO } from '../lib/format.js';
import { bpZuText, textZuBp } from '../lib/privat.js';

export default function Afa() {
  const { gewerbeId, jahr, jahrAbgeschlossen } = useOutletContext();
  const [afaKategorien, setAfaKategorien] = useState([]);
  // Kategorie-Key -> EÜR-Zeile im gewählten Jahr (die Zeilen verschieben sich jährlich)
  const [zeilen, setZeilen] = useState({});
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
      setZeilen(Object.fromEntries(kat.data.map((k) => [k.key, k.euer_zeile])));
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

  const zeile = (key) => (zeilen[key] ? `Zeile ${zeilen[key]}` : 'der EÜR');

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
      methode: 'linear',
      bpInput: '',
      linearAb: '',
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
        sub={`Teure Anschaffungen über mehrere Jahre absetzen · Jahres-AfA ${jahr} fließt in ${zeile('afa_beweglich')}.`}
      >
        <button className="btn-primary" onClick={openNew}>
          <IconPlus className="mr-1 h-4 w-4" /> Anschaffung
        </button>
      </PageHeader>
      <AbschlussHinweis jahr={jahr} abgeschlossen={jahrAbgeschlossen} />

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
        <p>
          <strong>Abschreibung:</strong> Standard ist <strong>linear</strong>. Für Anschaffungen vom 01.07.2025 bis
          31.12.2027 geht auch <strong>degressiv</strong> (bis zu 30 %, höchstens das Dreifache des linearen Satzes),
          für reine Elektrofahrzeuge die <strong>Staffel 75/10/5/5/3/2 %</strong>, und für Anschaffungen von 250,01
          bis 1.000 € der <strong>Sammelposten</strong> (je ein Fünftel in fünf Jahren). Tab zeigt dir beim Anlegen
          den kompletten Plan.
        </p>
      </Hinweis>

      <Kennzahlen cols={1} className="mt-6">
        <Kennzahl label={`Summe Jahres-AfA ${jahr} (${zeile('afa_beweglich')})`} value={formatEuro(sumJahresAfa)} />
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
                  <span>{methodeLabel(a)}</span>
                  {a.abgang_datum && (
                    <>
                      {PUNKT}
                      <span>
                        Abgang {formatDateDE(a.abgang_datum)}
                        {a.restbuchwert_cent > 0 && (
                          <> · Restbuchwert {formatEuro(a.restbuchwert_cent)} → als Buchung {zeile('restbuchwert')} erfassen</>
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
            >
              {a.verlauf?.length > 1 && (
                <details className="mt-1 text-[13px] text-ink/70">
                  <summary className="cursor-pointer select-none font-bold text-royal">AfA-Plan</summary>
                  <PlanTabelle verlauf={a.verlauf} aktuellesJahr={jahr} />
                </details>
              )}
            </Row>
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

// Kurzbeschreibung der Abschreibung für die Zustandszeile
function methodeLabel(a) {
  const m = a.afa_methode || 'linear';
  if (m === 'degressiv') return `${a.methode_text}, ${a.nutzungsdauer_jahre} Jahre`;
  if (m === 'elektro') return 'Elektro-Staffel';
  if (m === 'sammelposten') return 'Sammelposten';
  return a.nutzungsdauer_jahre === 1 ? 'Sofortabzug' : `${a.nutzungsdauer_jahre} Jahre linear`;
}

// AfA je Jahr mit Restbuchwert (Plan der Anlage bzw. Vorschau im Formular)
function PlanTabelle({ verlauf, aktuellesJahr, max = 12 }) {
  const zeilen = verlauf.slice(0, max);
  return (
    <div className="mt-1.5 max-w-md">
      {zeilen.map((z) => (
        <div
          key={z.jahr}
          className={`grid grid-cols-[3.5rem_1fr_1fr_auto] items-baseline gap-x-3 py-0.5 tabular-nums ${z.jahr === aktuellesJahr ? 'font-bold text-ink' : ''}`}
        >
          <span>{z.jahr}</span>
          <span className="text-right">{formatEuro(z.afa_cent)}</span>
          <span className="text-right text-ink/60">Rest {formatEuro(z.buchwert_cent)}</span>
          <span className="w-12 text-xs text-ink/50">{z.linear && verlauf.some((x) => !x.linear) ? 'linear' : ''}</span>
        </div>
      ))}
      {verlauf.length > max && <div className="py-0.5 text-ink/60">… und {verlauf.length - max} weitere Jahre</div>}
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
    sofort: (a.afa_methode || 'linear') === 'linear' && a.nutzungsdauer_jahre === 1,
    methode: a.afa_methode || 'linear',
    bpInput: bpZuText(a.degressiv_bp || 0),
    linearAb: a.linear_ab_jahr ? String(a.linear_ab_jahr) : '',
    abgang: Boolean(a.abgang_datum),
    abgang_datum: a.abgang_datum || '',
    beschreibung: a.beschreibung || '',
  };
}

const METHODEN_HINWEIS = {
  linear: 'Gleichmäßig über die Nutzungsdauer, monatsgenau ab dem Anschaffungsmonat.',
  degressiv:
    'Fester Satz vom Restwert: am Anfang mehr, später weniger. Tab wechselt zur linearen AfA, sobald sie höher ist.',
  elektro: 'Für reine Elektrofahrzeuge: 75 % im ersten Jahr (egal in welchem Monat), danach 10, 5, 5, 3 und 2 %.',
  sammelposten: 'Für Anschaffungen von 250,01 bis 1.000 €: je ein Fünftel im Anschaffungsjahr und den vier Jahren danach.',
};

function AfaModal({ editing, setEditing, afaKategorien, gewerbeId, onSaved }) {
  const [busy, setBusy] = useState(false);
  const [optionen, setOptionen] = useState(null);
  const [plan, setPlan] = useState(null); // { ok, verlauf, hinweise } | { ok: false, fehler }
  const options = afaKategorien.map((k) => ({
    value: String(k.id),
    label: k.euer_zeile ? `${k.name} · Zeile ${k.euer_zeile}` : k.name,
  }));

  const methode = editing.methode || 'linear';
  const festeDauer = methode === 'elektro' || methode === 'sammelposten';
  const nd = festeDauer ? (methode === 'elektro' ? 6 : 5) : editing.sofort && methode === 'linear' ? 1 : Number(editing.nutzungsdauer_jahre);
  const bp = textZuBp(editing.bpInput);
  const linearAb = editing.linearAb ? Number(editing.linearAb) : null;
  const kosten = parseEuroToCent(editing.kostenInput);

  // Welche Methoden für dieses Datum und diese Nutzungsdauer zulässig sind (entscheidet das Backend)
  useEffect(() => {
    if (!editing.anschaffungsdatum || !(nd >= 1)) return undefined;
    let aktiv = true;
    api
      .get('/api/afa/optionen', { params: { anschaffungsdatum: editing.anschaffungsdatum, nutzungsdauer_jahre: nd } })
      .then((res) => {
        if (!aktiv) return;
        setOptionen(res.data);
        const o = res.data;
        if ((methode === 'degressiv' && !o.degressiv.moeglich) || (methode === 'elektro' && !o.elektro.moeglich)) {
          toast('Diese Abschreibung gilt für das gewählte Datum nicht — Tab nimmt linear.', { duration: 6000 });
          setEditing((e) => ({ ...e, methode: 'linear', bpInput: '', linearAb: '' }));
        } else if (methode === 'degressiv') {
          const max = o.degressiv.max_bp;
          // Satz leer oder über dem Höchstsatz: Höchstsatz einsetzen
          if (!textZuBp(editing.bpInput) || textZuBp(editing.bpInput) > max)
            setEditing((e) => ({ ...e, bpInput: bpZuText(max) }));
        }
      })
      .catch(() => {});
    return () => {
      aktiv = false;
    };
  }, [editing.anschaffungsdatum, nd, methode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Plan-Vorschau (nichts wird gespeichert)
  useEffect(() => {
    if (!kosten || kosten <= 0 || !editing.anschaffungsdatum || !(nd >= 1)) {
      setPlan(null);
      return undefined;
    }
    let aktiv = true;
    const t = setTimeout(() => {
      api
        .post('/api/afa/vorschau', {
          anschaffungskosten_cent: kosten,
          anschaffungsdatum: editing.anschaffungsdatum,
          nutzungsdauer_jahre: nd,
          abgang_datum: editing.abgang && editing.abgang_datum ? editing.abgang_datum : null,
          afa_methode: methode,
          degressiv_bp: methode === 'degressiv' ? bp : null,
          linear_ab_jahr: methode === 'degressiv' ? linearAb : null,
        })
        .then((res) => aktiv && setPlan({ ok: true, ...res.data }))
        .catch((e) => aktiv && setPlan({ ok: false, fehler: apiError(e) }));
    }, 300);
    return () => {
      aktiv = false;
      clearTimeout(t);
    };
  }, [kosten, editing.anschaffungsdatum, nd, methode, bp, linearAb, editing.abgang, editing.abgang_datum]);

  const methodenOptionen = [
    { value: 'linear', label: 'Linear' },
    ...(optionen?.degressiv.moeglich || methode === 'degressiv' ? [{ value: 'degressiv', label: 'Degressiv' }] : []),
    ...(optionen?.elektro.moeglich || methode === 'elektro' ? [{ value: 'elektro', label: 'Elektrofahrzeug (Staffel)' }] : []),
    { value: 'sammelposten', label: 'Sammelposten' },
  ];

  function waehleMethode(m) {
    setEditing({
      ...editing,
      methode: m,
      sofort: m === 'linear' ? editing.sofort : false,
      bpInput: m === 'degressiv' ? bpZuText(optionen?.degressiv.max_bp || 0) : '',
      linearAb: '',
      nutzungsdauer_jahre: m === 'degressiv' && Number(editing.nutzungsdauer_jahre) < 2 ? 3 : editing.nutzungsdauer_jahre,
    });
  }

  async function save(e) {
    e.preventDefault();
    if (!editing.bezeichnung.trim()) return toast.error('Bezeichnung ist Pflicht.');
    if (!editing.kategorie_id) return toast.error('Bitte AfA-Kategorie wählen.');
    if (!kosten || kosten <= 0) return toast.error('Bitte gültige Anschaffungskosten eingeben.');
    if (!nd || nd < 1) return toast.error('Nutzungsdauer muss mindestens 1 Jahr sein.');
    if (methode === 'degressiv' && bp === null) return toast.error('Bitte den degressiven Satz in % angeben.');
    if (methode === 'degressiv' && editing.linearAb && !Number.isInteger(linearAb)) return toast.error('„Linear ab Jahr“ ist keine gültige Jahreszahl.');
    if (editing.abgang && !editing.abgang_datum) return toast.error('Bitte Abgangsdatum angeben.');

    const body = {
      gewerbe_id: Number(gewerbeId),
      kategorie_id: Number(editing.kategorie_id),
      bezeichnung: editing.bezeichnung.trim(),
      anschaffungskosten_cent: kosten,
      anschaffungsdatum: editing.anschaffungsdatum,
      nutzungsdauer_jahre: nd,
      afa_methode: methode,
      degressiv_bp: methode === 'degressiv' ? bp : null,
      linear_ab_jahr: methode === 'degressiv' ? linearAb : null,
      abgang_datum: editing.abgang ? editing.abgang_datum : null,
      beschreibung: editing.beschreibung.trim() || null,
    };
    setBusy(true);
    try {
      let res;
      if (editing.id) {
        res = await api.patch(`/api/afa/${editing.id}`, body);
        toast.success('Gespeichert.');
      } else {
        res = await api.post('/api/afa', body);
        toast.success('Wirtschaftsgut angelegt.');
      }
      for (const h of res.data.hinweise || []) toast(h, { duration: 9000 });
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

        <div className="block">
          <span className="field-label">Abschreibung</span>
          <Dropdown value={methode} onChange={(v) => waehleMethode(String(v))} options={methodenOptionen} />
          <span className="mt-1 block text-xs text-ink/60">
            {METHODEN_HINWEIS[methode]}
            {methode === 'linear' && optionen && !optionen.degressiv.moeglich && !optionen.elektro.moeglich
              ? ' Degressiv und die Elektro-Staffel gibt es nur für Anschaffungen vom 01.07.2025 bis 31.12.2027.'
              : ''}
          </span>
        </div>

        {methode === 'linear' && (
          <SchalterZeile
            titel="Sofortabzug (Nutzungsdauer 1 Jahr)"
            hinweis="Für Computer-Hardware und Software."
            checked={editing.sofort}
            onChange={(an) => setEditing({ ...editing, sofort: an })}
          />
        )}

        {!festeDauer && !(methode === 'linear' && editing.sofort) && (
          <label className="block">
            <span className="field-label">Nutzungsdauer (Jahre)</span>
            <input
              type="number"
              min={methode === 'degressiv' ? 2 : 1}
              max="50"
              className="input tabular-nums"
              value={editing.nutzungsdauer_jahre}
              onChange={(e) => setEditing({ ...editing, nutzungsdauer_jahre: e.target.value })}
            />
          </label>
        )}

        {methode === 'degressiv' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
            <label className="block">
              <span className="field-label">Degressiver Satz (%)</span>
              <input
                className="input tabular-nums"
                inputMode="decimal"
                value={editing.bpInput}
                onChange={(e) => setEditing({ ...editing, bpInput: e.target.value })}
                placeholder="z. B. 30"
              />
              <span className="mt-1 block text-xs text-ink/60">
                {optionen?.degressiv.max_bp ? `Höchstens ${bpZuText(optionen.degressiv.max_bp)} % möglich.` : ' '}
              </span>
            </label>
            <label className="block">
              <span className="field-label">Linear ab Jahr (optional)</span>
              <input
                className="input tabular-nums"
                inputMode="numeric"
                value={editing.linearAb}
                onChange={(e) => setEditing({ ...editing, linearAb: e.target.value.replace(/\D/g, '').slice(0, 4) })}
                placeholder="früherer Wechsel"
              />
              <span className="mt-1 block text-xs text-ink/60">Sonst wechselt Tab selbst, sobald linear mehr ist.</span>
            </label>
          </div>
        )}

        {plan && (
          <Gruppe titel="AfA-Plan">
            {plan.ok ? (
              <>
                <PlanTabelle verlauf={plan.verlauf} aktuellesJahr={Number(editing.anschaffungsdatum.slice(0, 4))} />
                {plan.hinweise?.map((h) => (
                  <Hinweis key={h} ton="warn" className="!py-2 text-xs">
                    {h}
                  </Hinweis>
                ))}
              </>
            ) : (
              <Hinweis ton="warn" className="!py-2 text-xs">
                {plan.fehler}
              </Hinweis>
            )}
          </Gruppe>
        )}

        <div>
          <SchalterZeile
            titel="Abgang (Verkauf / Entnahme / Verschrottung)"
            checked={editing.abgang}
            onChange={(an) => setEditing({ ...editing, abgang: an })}
          />
          {editing.abgang && (
            <div className="mt-3 space-y-3">
              <label className="block">
                <span className="field-label">Abgangsdatum</span>
                <input
                  type="date"
                  className="input"
                  value={editing.abgang_datum}
                  onChange={(e) => setEditing({ ...editing, abgang_datum: e.target.value })}
                />
              </label>
              <Hinweis>
                {methode === 'sammelposten'
                  ? 'Beim Sammelposten ändert ein Abgang nichts: Die Fünftel laufen weiter, es gibt keinen Restbuchwert.'
                  : 'Die AfA endet mit dem Abgangsmonat. Den Restbuchwert (wird in der Liste angezeigt) als Buchung „Restbuchwert" erfassen, einen Verkaufserlös als „Veräußerung Anlagevermögen".'}
              </Hinweis>
            </div>
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

        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            Speichern
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}
