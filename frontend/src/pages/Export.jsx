import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro } from '../lib/format.js';

function NoGewerbe() {
  return (
    <div className="card p-12 text-center text-ink/60">
      Kein Gewerbe gewählt. Lege unter „Gewerbe" zuerst ein Gewerbe an.
    </div>
  );
}

export default function Export() {
  const { gewerbeId, jahr, gewerbe } = useOutletContext();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState('');

  const gewerbeName = gewerbe.find((g) => String(g.id) === String(gewerbeId))?.name || 'gewerbe';

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/api/export/summenblatt', {
        params: { gewerbe_id: gewerbeId, jahr },
      });
      setData(res.data);
    } catch (e) {
      setData(null);
      setError(apiError(e, 'Summenblatt konnte nicht erstellt werden.'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  const DOWNLOADS = {
    summenblatt: { url: '/api/export/summenblatt.csv', name: () => `euer-summenblatt-${slug()}-${jahr}.csv` },
    journal: { url: '/api/export/journal.csv', name: () => `beleg-journal-${slug()}-${jahr}.csv` },
    archiv: { url: '/api/export/belege.zip', name: () => `euer-archiv-${slug()}-${jahr}.zip` },
    backup: { url: '/api/export/backup.zip', name: () => 'tab-backup.zip', noParams: true },
  };

  function slug() {
    return gewerbeName.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  }

  async function download(kind) {
    setDownloading(kind);
    const d = DOWNLOADS[kind];
    try {
      const res = await api.get(d.url, {
        params: d.noParams ? {} : { gewerbe_id: gewerbeId, jahr },
        responseType: 'blob',
      });
      const href = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = href;
      a.download = d.name();
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
    } catch (e) {
      toast.error(apiError(e, 'Download fehlgeschlagen.'));
    } finally {
      setDownloading('');
    }
  }

  if (!gewerbeId) return <NoGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight">EÜR-Export {jahr}</h1>
        <p className="text-xs text-ink/60 mt-0.5">
          {gewerbeName} · Summen zum Übertragen ins Steuerprogramm/ELSTER. Kein Direktversand.
        </p>
      </div>

      {data?.vorlaeufig && (
        <div className="p-4 rounded flex items-start gap-3 bg-yellow-100 text-yellow-900">
          <div>
            <div className="font-bold">Vorläufiges Mapping für {jahr}</div>
            <div className="text-sm mt-0.5">
              Der amtliche Vordruck {jahr} liegt noch nicht final vor — die Zeilen sind eine Kopie
              von 2025. Vor Abgabe gegen den aktuellen Vordruck abgleichen. ({data.quelle})
            </div>
            <div className="text-sm mt-1.5 font-medium">
              {new Date() >= new Date(jahr, 9, 1)
                ? `Die amtliche Anleitung ${jahr} sollte inzwischen veröffentlicht sein (BMF/ELSTER, üblicherweise ab Herbst) — jetzt Mapping abgleichen und scharfstellen.`
                : `Die amtliche Anleitung ${jahr} erscheint erfahrungsgemäß im Herbst ${jahr}; abgeben musst du erst ${jahr + 1} — bis dahin ist das vorläufige Mapping okay.`}
            </div>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row gap-2 no-print">
        <button
          className="btn-primary w-full sm:w-auto"
          onClick={() => download('summenblatt')}
          disabled={downloading !== '' || !data}
        >
          {downloading === 'summenblatt' ? 'Lädt…' : 'Summenblatt als CSV'}
        </button>
        <button
          className="btn-outline w-full sm:w-auto"
          onClick={() => download('journal')}
          disabled={downloading !== ''}
        >
          {downloading === 'journal' ? 'Lädt…' : 'Beleg-Journal als CSV'}
        </button>
        <button
          className="btn-outline w-full sm:w-auto"
          onClick={() => window.print()}
          disabled={!data || data.zeilen.length === 0}
        >
          Drucken / PDF
        </button>
        <button
          className="btn-outline w-full sm:w-auto"
          onClick={() => download('archiv')}
          disabled={downloading !== '' || !data}
          title="Summenblatt + Journal + alle Beleg-Dateien des Jahres als ZIP"
        >
          {downloading === 'archiv' ? 'Lädt…' : 'Jahres-Archiv (ZIP)'}
        </button>
        <button
          className="btn-ghost w-full sm:w-auto"
          onClick={() => download('backup')}
          disabled={downloading !== ''}
          title="Komplett-Backup: Datenbank + alle Beleg-Dateien"
        >
          {downloading === 'backup' ? 'Lädt…' : 'Backup'}
        </button>
      </div>

      {error ? (
        <div className="p-4 rounded flex items-start gap-3 bg-red-50 border-l-4 border-red-500 text-red-900">
          <div>
            <div className="font-bold">Kein Summenblatt</div>
            <div className="text-sm mt-0.5">{error}</div>
          </div>
        </div>
      ) : data && data.zeilen.length === 0 ? (
        <div className="card p-12 text-center text-ink/60">
          Keine befüllten Zeilen für {jahr}. Erfasse zuerst Buchungen oder AfA.
        </div>
      ) : data ? (
        <div className="print-area space-y-3">
          <div className="hidden print:block">
            <h2 className="text-xl font-black">EÜR-Summenblatt {jahr}</h2>
            <div className="text-sm text-ink/70">
              {gewerbeName}
              {data.gewerbe.steuernummer ? ` · St.-Nr. ${data.gewerbe.steuernummer}` : ''} ·
              Kleinunternehmer §19 UStG
              {data.vorlaeufig ? ' · vorläufiges Mapping' : ''}
            </div>
          </div>
          <div className="card overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-ink/60 text-xs uppercase tracking-wider">
              <tr className="border-b border-ink/10">
                <th className="px-4 py-3 w-20">Zeile</th>
                <th className="px-4 py-3">Bezeichnung</th>
                <th className="px-4 py-3 text-right">Betrag</th>
              </tr>
            </thead>
            <tbody>
              {data.zeilen.map((z) => (
                <tr key={z.nummer} className="border-b border-ink/5">
                  <td className="px-4 py-3 tabular-nums font-bold">{z.nummer}</td>
                  <td className="px-4 py-3">
                    {z.bezeichnung}
                    {z.typ === 'einnahme' && (
                      <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full bg-royal-soft/40 text-ink text-[10px] font-bold uppercase tracking-wider">
                        Einnahme
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">
                    {formatEuro(z.betrag_cent)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t border-ink/10">
              <tr>
                <td className="px-4 py-3" />
                <td className="px-4 py-3 font-bold">Summe Betriebseinnahmen (Zeile 23)</td>
                <td className="px-4 py-3 text-right tabular-nums font-bold">
                  {formatEuro(data.summe_einnahmen_cent)}
                </td>
              </tr>
              <tr>
                <td className="px-4 py-3" />
                <td className="px-4 py-3 font-bold">Summe Betriebsausgaben</td>
                <td className="px-4 py-3 text-right tabular-nums font-bold">
                  {formatEuro(data.summe_ausgaben_cent)}
                </td>
              </tr>
              <tr className="bg-royal-soft/10">
                <td className="px-4 py-3" />
                <td className="px-4 py-3 font-black">Gewinn / Verlust</td>
                <td className="px-4 py-3 text-right tabular-nums font-black">
                  {formatEuro(data.gewinn_cent)}
                </td>
              </tr>
            </tfoot>
          </table>
          </div>
        </div>
      ) : null}
    </div>
  );
}
