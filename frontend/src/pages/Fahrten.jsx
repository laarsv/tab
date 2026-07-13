import { useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro, formatDateDE, todayISO } from '../lib/format.js';

function NoGewerbe() {
  return (
    <div className="card p-12 text-center text-ink/60">
      Kein Gewerbe gewählt. Lege unter „Gewerbe" zuerst ein Gewerbe an.
    </div>
  );
}

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

  if (!gewerbeId) return <NoGewerbe />;
  if (loading) return <PageSpinner />;

  const fahrtKat = kategorien.find((k) => k.key === 'fahrtkosten_kfz');

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Fahrten-Liste {jahr}</h1>
        <p className="text-xs text-ink/60 mt-0.5">
          Betriebliche Fahrten mit dem Privatwagen sammeln (Datum, Ziel, Anlass, km) — der
          Nachweis für die km-Pauschale. Kein Fahrtenbuch für die 1 %-Regelung.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="card p-4">
          <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">
            Summe {jahr}
          </div>
          <div className="text-xl font-black tabular-nums mt-1">
            {String(data.summe_km).replace('.', ',')} km · {formatEuro(data.betrag_cent)}
          </div>
          <div className="text-[11px] text-ink/50 mt-0.5">× 0,30 €/km</div>
        </div>
        <div className="card p-4 flex flex-col justify-center items-start gap-2">
          <button
            className="btn-primary btn-sm"
            disabled={!data.fahrten.length || !fahrtKat}
            onClick={() => setUebernehmen(true)}
          >
            Summe als Buchung übernehmen
          </button>
          <span className="text-xs text-ink/60">
            Am besten einmal am Jahresende — nicht zusätzlich zu schon gebuchten Fahrtkosten
            (sonst doppelt).
          </span>
        </div>
      </div>

      <form onSubmit={add} className="card p-4 grid grid-cols-2 sm:grid-cols-5 gap-x-5 gap-y-2 items-end">
        <label className="block">
          <span className="field-label">Datum</span>
          <input type="date" className="input" value={form.datum} onChange={(e) => setForm({ ...form, datum: e.target.value })} />
        </label>
        <label className="block col-span-2 sm:col-span-1">
          <span className="field-label">Ziel / Strecke</span>
          <input className="input" value={form.ziel} onChange={(e) => setForm({ ...form, ziel: e.target.value })} placeholder="z. B. Kunde Meier, HH" />
        </label>
        <label className="block col-span-2 sm:col-span-1">
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
        <div className="card p-12 text-center text-ink/60">
          Noch keine Fahrten für {jahr}. Tipp: direkt nach der Fahrt eintragen — auf dem Handy
          dauert's zehn Sekunden.
        </div>
      ) : (
        <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-ink/60 text-xs uppercase tracking-wider">
              <tr className="border-b border-ink/10">
                <th className="px-4 py-3">Datum</th>
                <th className="px-4 py-3">Ziel / Strecke</th>
                <th className="px-4 py-3 hidden sm:table-cell">Anlass</th>
                <th className="px-4 py-3 text-right">km</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {data.fahrten.map((f) => (
                <tr key={f.id} className="border-b border-ink/5 last:border-b-0">
                  <td className="px-4 py-2.5 whitespace-nowrap">{formatDateDE(f.datum)}</td>
                  <td className="px-4 py-2.5">{f.ziel}</td>
                  <td className="px-4 py-2.5 text-ink/60 hidden sm:table-cell">{f.anlass || '—'}</td>
                  <td className="px-4 py-2.5 text-right tabular-nums">{String(f.km).replace('.', ',')}</td>
                  <td className="px-4 py-2.5 text-right">
                    <button className="btn-ghost btn-sm text-red-700" onClick={() => remove(f)}>
                      Löschen
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-xs text-ink/50">
        Die Liste wandert automatisch als <code>fahrten-{jahr}.csv</code> ins{' '}
        <Link to="/export" className="text-royal hover:underline">Jahres-Archiv (ZIP)</Link>.
      </p>

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
