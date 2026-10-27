import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import { IconButton, IconPin, IconTrash } from '../components/Icons.jsx';
import {
  Hinweis,
  KeinGewerbe,
  Kennzahl,
  Kennzahlen,
  Leer,
  PageHeader,
  PUNKT,
  Row,
  SectionHead,
} from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro, formatDateDE, todayISO } from '../lib/format.js';

const MONATE = [
  'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
  'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
];

const kmText = (km) => String(km).replace('.', ',');

function emptyForm() {
  return { datum: todayISO(), ziel: '', anlass: '', km: '' };
}

export default function Fahrten() {
  const { gewerbeId, jahr, reloadBadges } = useOutletContext();
  const [data, setData] = useState({ fahrten: [], summe_km: 0, betrag_cent: 0 });
  const [kategorien, setKategorien] = useState([]);
  const [form, setForm] = useState(emptyForm());
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [uebernehmen, setUebernehmen] = useState(false);

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [f, kat] = await Promise.all([
        api.get('/api/fahrten', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/kategorien', { params: { jahr } }),
      ]);
      setData(f.data);
      setKategorien(kat.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  async function add(e) {
    e.preventDefault();
    const km = Number(String(form.km).replace(',', '.'));
    if (!form.ziel.trim()) return toast.error('Bitte Ziel/Strecke angeben.');
    if (!Number.isFinite(km) || km <= 0) return toast.error('Bitte gültige km angeben.');
    setBusy(true);
    try {
      await api.post('/api/fahrten', {
        gewerbe_id: Number(gewerbeId),
        datum: form.datum,
        ziel: form.ziel.trim(),
        anlass: form.anlass.trim() || null,
        km,
      });
      setForm((f) => ({ ...emptyForm(), datum: f.datum })); // Datum behalten für Serien-Eingabe
      await load();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  async function remove(f) {
    try {
      await api.delete(`/api/fahrten/${f.id}`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (loading) return <PageSpinner />;

  const fahrtKat = kategorien.find((k) => k.key === 'fahrtkosten_kfz');

  // Nach Monat gruppieren (neueste zuerst), je Monat die Summe km.
  const gruppen = [];
  for (const f of data.fahrten) {
    const k = f.datum.slice(0, 7);
    let g = gruppen.find((x) => x.k === k);
    if (!g) {
      g = { k, liste: [], km: 0 };
      gruppen.push(g);
    }
    g.liste.push(f);
    g.km += Number(f.km) || 0;
  }

  return (
    <div>
      <PageHeader
        title="Fahrten-Liste"
        accent={jahr}
        sub="Betriebliche Fahrten mit dem Privatwagen sammeln (Datum, Ziel, Anlass, km) — der Nachweis für die km-Pauschale. Kein Fahrtenbuch für die 1 %-Regelung."
      >
        <button
          className="btn-primary btn-sm"
          disabled={!data.fahrten.length || !fahrtKat}
          onClick={() => setUebernehmen(true)}
        >
          Summe als Buchung übernehmen
        </button>
      </PageHeader>

      <Kennzahlen cols={1} className="mt-6">
        <Kennzahl
          label={`Summe ${jahr}`}
          value={`${kmText(data.summe_km)} km · ${formatEuro(data.betrag_cent)}`}
          hint="× 0,30 €/km — am besten einmal am Jahresende übernehmen, nicht zusätzlich zu schon gebuchten Fahrtkosten (sonst doppelt)"
        />
      </Kennzahlen>

      <SectionHead label="Neue Fahrt" />
      <form
        onSubmit={add}
        className="grid grid-cols-2 items-end gap-x-5 gap-y-2 rounded-xl bg-surface p-4 sm:grid-cols-5"
      >
        <label className="block">
          <span className="field-label">Datum</span>
          <input type="date" className="input" value={form.datum} onChange={(e) => setForm({ ...form, datum: e.target.value })} />
        </label>
        <label className="col-span-2 block sm:col-span-1">
          <span className="field-label">Ziel / Strecke</span>
          <input className="input" value={form.ziel} onChange={(e) => setForm({ ...form, ziel: e.target.value })} placeholder="z. B. Kunde Meier, HH" />
        </label>
        <label className="col-span-2 block sm:col-span-1">
          <span className="field-label">Anlass (optional)</span>
          <input className="input" value={form.anlass} onChange={(e) => setForm({ ...form, anlass: e.target.value })} placeholder="z. B. Beratung" />
        </label>
        <label className="block">
          <span className="field-label">km (hin+zurück)</span>
          <input className="input tabular-nums" inputMode="decimal" value={form.km} onChange={(e) => setForm({ ...form, km: e.target.value })} placeholder="z. B. 46" />
        </label>
        <button type="submit" className="btn-primary" disabled={busy}>
          + Fahrt
        </button>
      </form>

      {data.fahrten.length === 0 ? (
        <Leer>
          Noch keine Fahrten für {jahr}. Tipp: direkt nach der Fahrt eintragen — auf dem Handy dauert's zehn
          Sekunden.
        </Leer>
      ) : (
        gruppen.map((g) => (
          <section key={g.k} aria-label={`${MONATE[Number(g.k.slice(5, 7)) - 1]} ${g.k.slice(0, 4)}`}>
            <SectionHead label={`${MONATE[Number(g.k.slice(5, 7)) - 1]} ${g.k.slice(0, 4)}`} count={g.liste.length}>
              <span className="text-sm font-bold tabular-nums text-ink/60">{kmText(g.km)} km</span>
            </SectionHead>
            {g.liste.map((f) => (
              <Row
                key={f.id}
                icon={IconPin}
                title={f.ziel}
                sub={
                  <>
                    <span className="tabular-nums">{formatDateDE(f.datum)}</span>
                    {f.anlass && (
                      <>
                        {PUNKT}
                        <span>{f.anlass}</span>
                      </>
                    )}
                  </>
                }
                amount={`${kmText(f.km)} km`}
                actions={<IconButton icon={IconTrash} variant="danger" label="Fahrt löschen" onClick={() => remove(f)} />}
              />
            ))}
          </section>
        ))
      )}

      <Hinweis className="mt-8">
        Die Liste wandert automatisch als <code>fahrten-{jahr}.csv</code> ins{' '}
        <Link to="/export" className="font-medium text-royal hover:underline">
          Jahres-Archiv (ZIP)
        </Link>
        .
      </Hinweis>

      {uebernehmen && (
        <BuchungModal
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          presetKategorieId={fahrtKat?.id}
          presetBetragCent={data.betrag_cent}
          presetBeschreibung={`Fahrtkosten laut Fahrten-Liste ${jahr} (${String(data.summe_km).replace('.', ',')} km × 0,30 €)`}
          onClose={() => setUebernehmen(false)}
          onSaved={async () => {
            await load();
            reloadBadges?.();
          }}
        />
      )}
    </div>
  );
}
