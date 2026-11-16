import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { IconArchive, IconButton, IconDownload, IconFileText, IconPrinter } from '../components/Icons.jsx';
import { Hinweis, KeinGewerbe, Kennzahl, Kennzahlen, Leer, PageHeader, Row, SectionHead } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro } from '../lib/format.js';
import { istBilanz } from '../lib/gewinnermittlung.js';
import { Link } from 'react-router-dom';

export default function Export() {
  const { gewerbeId, jahr, gewerbe } = useOutletContext();
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState('');

  const gewerbeName = gewerbe.find((g) => String(g.id) === String(gewerbeId))?.name || 'gewerbe';
  const bilanzJahr = istBilanz(gewerbe.find((g) => String(g.id) === String(gewerbeId)), jahr);

  async function load() {
    if (!gewerbeId || bilanzJahr) {
      setData(null);
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
  }, [gewerbeId, jahr, bilanzJahr]); // eslint-disable-line react-hooks/exhaustive-deps

  // DATEV: Einstellungen da? Hinweise zur Kontierung?
  const [datev, setDatev] = useState(null);
  useEffect(() => {
    if (!gewerbeId) return;
    api
      .get('/api/export/datev', { params: { gewerbe_id: gewerbeId, jahr } })
      .then((r) => setDatev(r.data))
      .catch(() => setDatev(null));
  }, [gewerbeId, jahr]);

  const DOWNLOADS = {
    summenblatt: { url: '/api/export/summenblatt.csv', name: () => `euer-summenblatt-${slug()}-${jahr}.csv` },
    journal: { url: '/api/export/journal.csv', name: () => `beleg-journal-${slug()}-${jahr}.csv` },
    archiv: { url: '/api/export/belege.zip', name: () => `euer-archiv-${slug()}-${jahr}.zip` },
    backup: { url: '/api/export/backup.zip', name: () => 'tab-backup.zip', noParams: true },
    datev: { url: '/api/export/datev.csv', name: () => `EXTF_Buchungsstapel_${slug()}_${jahr}.csv` },
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

  if (!gewerbeId) return <KeinGewerbe />;
  if (loading) return <PageSpinner />;

  const laedt = downloading !== '';
  const AKTIONEN = [
    {
      key: 'summenblatt',
      icon: IconFileText,
      titel: 'Summenblatt (CSV)',
      text: 'Die Summen je Zeile der Anlage EÜR — zum Übertragen ins Steuerprogramm.',
      disabled: laedt || !data,
      primary: true,
      run: () => download('summenblatt'),
    },
    {
      key: 'journal',
      icon: IconFileText,
      titel: 'Beleg-Journal (CSV)',
      text: 'Jede Buchung mit Kategorie und Zeile — zum Gegenprüfen, auch durch den Steuerberater.',
      disabled: laedt,
      run: () => download('journal'),
    },
    {
      key: 'datev',
      icon: IconFileText,
      titel: 'DATEV-Buchungsstapel',
      text: datev
        ? datev.bereit
          ? `${datev.zeilen} Buchungszeilen im ${datev.skr === '04' ? 'SKR04' : 'SKR03'} — für die Steuerberatung (DATEV-Format EXTF).`
          : datev.fehler
        : 'Für die Steuerberatung (DATEV-Format EXTF).',
      disabled: laedt || !datev?.bereit,
      run: () => download('datev'),
    },
    {
      key: 'druck',
      icon: IconPrinter,
      titel: 'Drucken / PDF',
      text: 'Druck-Ansicht des Summenblatts.',
      disabled: !data || data.zeilen.length === 0,
      run: () => window.print(),
    },
    {
      key: 'archiv',
      icon: IconArchive,
      titel: 'Jahres-Archiv (ZIP)',
      text: bilanzJahr ? 'Bilanz und GuV, Journal und alle Beleg-Dateien des Jahres.' : 'Summenblatt, Journal und alle Beleg-Dateien des Jahres.',
      disabled: laedt || (!data && !bilanzJahr),
      run: () => download('archiv'),
    },
    {
      key: 'backup',
      icon: IconArchive,
      titel: 'Backup',
      text: 'Komplett-Backup: Datenbank und alle Beleg-Dateien (alle Jahre).',
      disabled: laedt,
      run: () => download('backup'),
    },
  ].filter((a) => !bilanzJahr || (a.key !== 'summenblatt' && a.key !== 'druck'));

  return (
    <div>
      <PageHeader
        title="EÜR-Export"
        accent={jahr}
        sub={`${gewerbeName} · Summen zum Übertragen ins Steuerprogramm/ELSTER. Kein Direktversand · Abgabefrist für ${jahr} (ohne Steuerberater): 31.07.${jahr + 1}`}
      />

      <div className="no-print mt-5 space-y-3">
        {bilanzJahr && (
          <Hinweis ton="warn" titel={`${jahr} ist ein Bilanz-Jahr`}>
            Für Bilanz-Jahre gibt es keine Anlage EÜR. Bilanz und GuV stehen unter{' '}
            <Link to="/bilanz" className="text-royal underline">Bilanz</Link>; der DATEV-Stapel folgt dort dem Soll-Prinzip.
          </Hinweis>
        )}
        <Hinweis titel="Tab ist die bessere Excel-Liste — keine Steuerberatung.">
          Die Zuordnungen folgen der amtlichen Anleitung, aber dein Fall kann Besonderheiten haben. Prüfe die
          Zahlen vor der Abgabe selbst oder lass sie vom Steuerberater gegenchecken — das Beleg-Journal unten ist
          genau dafür gemacht.
        </Hinweis>

        {data?.vorlaeufig && (
          <Hinweis ton="warn" titel={`Vorläufiges Mapping für ${jahr}`}>
            Der amtliche Vordruck {jahr} liegt noch nicht final vor — die Zeilen sind eine Kopie von 2025. Vor
            Abgabe gegen den aktuellen Vordruck abgleichen. ({data.quelle})
            <div className="mt-1.5 font-medium">
              {new Date() >= new Date(jahr, 9, 1)
                ? `Die amtliche Anleitung ${jahr} sollte inzwischen veröffentlicht sein (BMF/ELSTER, üblicherweise ab Herbst) — jetzt Mapping abgleichen und scharfstellen.`
                : `Die amtliche Anleitung ${jahr} erscheint erfahrungsgemäß im Herbst ${jahr}; abgeben musst du erst ${jahr + 1} — bis dahin ist das vorläufige Mapping okay.`}
            </div>
          </Hinweis>
        )}
      </div>

      <div className="no-print">
        <SectionHead label="Herunterladen" />
        {datev?.hinweise?.length > 0 && (
          <Hinweis ton="warn" titel="DATEV-Export: bitte prüfen" className="mb-2">
            <ul className="list-disc pl-5">
              {datev.hinweise.map((h) => (
                <li key={h}>{h}</li>
              ))}
            </ul>
          </Hinweis>
        )}
        {AKTIONEN.map((a) => (
          <Row
            key={a.key}
            icon={a.icon}
            title={a.titel}
            sub={<span>{downloading === a.key ? 'Lädt…' : a.text}</span>}
            actions={
              <IconButton
                icon={a.key === 'druck' ? IconPrinter : IconDownload}
                variant={a.primary ? 'primary' : 'ghost'}
                label={a.key === 'druck' ? 'Drucken / PDF' : `${a.titel} herunterladen`}
                onClick={a.run}
                disabled={a.disabled}
              />
            }
          />
        ))}
      </div>

      {error ? (
        <Hinweis ton="neg" titel="Kein Summenblatt" className="no-print mt-6">
          {error}
        </Hinweis>
      ) : data && data.zeilen.length === 0 ? (
        <Leer>Keine befüllten Zeilen für {jahr}. Erfasse zuerst Buchungen oder AfA.</Leer>
      ) : data ? (
        <div className="print-area">
          <SectionHead label={`Summenblatt ${jahr}`} count={data.zeilen.length} className="no-print" />
          <div className="hidden print:block">
            <h2 className="text-xl font-black">EÜR-Summenblatt {jahr}</h2>
            <div className="text-sm text-ink/70">
              {gewerbeName}
              {data.gewerbe.steuernummer ? ` · St.-Nr. ${data.gewerbe.steuernummer}` : ''} · Kleinunternehmer §19
              UStG
              {data.vorlaeufig ? ' · vorläufiges Mapping' : ''}
            </div>
          </div>

          <Kennzahlen className="mb-1 print:mt-3">
            <Kennzahl label="Betriebseinnahmen (Z. 23)" value={formatEuro(data.summe_einnahmen_cent)} royal />
            <Kennzahl label="Betriebsausgaben" value={formatEuro(data.summe_ausgaben_cent)} />
            <Kennzahl label="Gewinn / Verlust" value={formatEuro(data.gewinn_cent)} />
          </Kennzahlen>

          {data.zeilen.map((z) => (
            <Row
              key={z.nummer}
              kind={z.typ === 'einnahme' ? 'in' : 'out'}
              leading={<span className="font-mono text-[13px] font-bold tabular-nums">{z.nummer}</span>}
              title={z.bezeichnung}
              wrapTitle
              sub={<span>{z.typ === 'einnahme' ? `Zeile ${z.nummer} · Einnahme` : `Zeile ${z.nummer}`}</span>}
              amount={formatEuro(z.betrag_cent)}
              amountIn={z.typ === 'einnahme'}
            />
          ))}

          <div className="hidden print:block pt-2 text-xs text-ink/50">
            Erstellt mit vrwb_tab — keine Steuerberatung, Angaben ohne Gewähr. Vor der Abgabe prüfen bzw. prüfen
            lassen.
          </div>
        </div>
      ) : null}
    </div>
  );
}
