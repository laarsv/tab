import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { IconArrowIn, IconArrowOut, IconDownload, IconFileText, IconReceipt, IconTrendDown } from '../components/Icons.jsx';
import { IconButton } from '../components/Icons.jsx';
import { Hinweis, Kennzahl, Kennzahlen, KeinGewerbe, Leer, PageHeader, PUNKT, Row, SectionHead, Zustand } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { openBeleg } from '../lib/belege.js';
import { formatDateDE, formatEuro } from '../lib/format.js';

// Ansicht der Steuerberatung (nur lesen): Auswertung · Buchungen · Rechnungen · Anlagen. Alle Daten kommen aus
// den lesenden Routen, die der Server für diese Rolle freigibt (auth/berater_guard.py).

const TABS = [
  ['auswertung', 'Auswertung'],
  ['buchungen', 'Buchungen'],
  ['rechnungen', 'Rechnungen'],
  ['anlagen', 'Anlagen'],
];

async function herunterladen(url, params, name, setBusy) {
  setBusy(true);
  try {
    const res = await api.get(url, { params, responseType: 'blob' });
    const href = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = href;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
  } catch (e) {
    toast.error(apiError(e, 'Download fehlgeschlagen.'));
  } finally {
    setBusy(false);
  }
}

async function pdfOeffnen(id) {
  try {
    const res = await api.get(`/api/rechnungen/${id}/pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    toast.error(apiError(e, 'PDF konnte nicht geöffnet werden.'));
  }
}

const STATUS = { versendet: 'versendet', bezahlt: 'bezahlt', storniert: 'storniert' };

export default function Berater() {
  const { gewerbeId, jahr, gewerbe } = useOutletContext();
  const [tab, setTab] = useState('auswertung');
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [fehler, setFehler] = useState('');
  const [dlBusy, setDlBusy] = useState(false);

  const firma = gewerbe.find((g) => String(g.id) === String(gewerbeId));
  const slug = (firma?.name || 'gewerbe').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  useEffect(() => {
    if (!gewerbeId) {
      setLoading(false);
      return undefined;
    }
    let aktiv = true;
    setLoading(true);
    setFehler('');
    const p = { gewerbe_id: gewerbeId, jahr };
    const ziel = {
      auswertung: () => api.get('/api/export/summenblatt', { params: p }),
      buchungen: () => api.get('/api/buchungen', { params: p }),
      rechnungen: () => api.get('/api/rechnungen', { params: p }),
      anlagen: () => api.get('/api/afa', { params: p }),
    }[tab];
    ziel()
      .then((r) => aktiv && setData((d) => ({ ...d, [tab]: r.data })))
      .catch((e) => {
        if (!aktiv) return;
        setData((d) => ({ ...d, [tab]: null }));
        setFehler(apiError(e, 'Laden fehlgeschlagen.'));
      })
      .finally(() => aktiv && setLoading(false));
    return () => {
      aktiv = false;
    };
  }, [gewerbeId, jahr, tab]);

  if (!gewerbeId) return <KeinGewerbe />;
  const d = data[tab];
  const dl = (url, name) => herunterladen(url, { gewerbe_id: gewerbeId, jahr }, name, setDlBusy);

  return (
    <div>
      <PageHeader title={firma?.name || 'Steuerberatung'} accent={jahr}
        sub={firma?.steuernummer ? `Steuernummer ${firma.steuernummer} · Kleinunternehmer § 19 UStG` : 'Kleinunternehmer § 19 UStG'} />

      <div className="mt-5 flex flex-wrap gap-2" role="tablist">
        {TABS.map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k}
            className={`${tab === k ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setTab(k)}>
            {label}
          </button>
        ))}
        <div className="ml-auto flex flex-wrap gap-2">
          <button type="button" className="btn-outline btn-sm" disabled={dlBusy}
            onClick={() => dl('/api/export/journal.csv', `beleg-journal-${slug}-${jahr}.csv`)}>
            <IconDownload className="mr-1 h-3.5 w-3.5" /> Journal (CSV)
          </button>
          <button type="button" className="btn-outline btn-sm" disabled={dlBusy}
            onClick={() => dl('/api/export/belege.zip', `euer-archiv-${slug}-${jahr}.zip`)}>
            <IconDownload className="mr-1 h-3.5 w-3.5" /> Jahresarchiv (ZIP)
          </button>
        </div>
      </div>

      {loading && !d ? (
        <PageSpinner />
      ) : fehler && !d ? (
        <Hinweis ton="neg" titel="Nicht verfügbar" className="mt-6">{fehler}</Hinweis>
      ) : tab === 'auswertung' && d ? (
        d.zeilen.length === 0 ? (
          <Leer>Für {jahr} gibt es noch keine befüllten Zeilen.</Leer>
        ) : (
          <>
            <Kennzahlen className="mt-6">
              <Kennzahl label="Betriebseinnahmen" value={formatEuro(d.summe_einnahmen_cent)} royal />
              <Kennzahl label="Betriebsausgaben" value={formatEuro(d.summe_ausgaben_cent)} />
              <Kennzahl label="Gewinn / Verlust" value={formatEuro(d.gewinn_cent)} />
            </Kennzahlen>
            <SectionHead label={`EÜR-Summenblatt ${jahr}`} count={d.zeilen.length}>
              <button type="button" className="btn-ghost btn-sm" disabled={dlBusy}
                onClick={() => dl('/api/export/summenblatt.csv', `euer-summenblatt-${slug}-${jahr}.csv`)}>
                CSV
              </button>
            </SectionHead>
            {d.zeilen.map((z) => (
              <Row key={z.nummer} kind={z.typ === 'einnahme' ? 'in' : 'out'}
                leading={<span className="font-mono text-[13px] font-bold tabular-nums">{z.nummer}</span>}
                title={z.bezeichnung} wrapTitle sub={<span>Zeile {z.nummer}</span>}
                amount={formatEuro(z.betrag_cent)} amountIn={z.typ === 'einnahme'} />
            ))}
          </>
        )
      ) : tab === 'buchungen' && d ? (
        d.length === 0 ? (
          <Leer>Keine Buchungen für {jahr}.</Leer>
        ) : (
          <>
            <SectionHead label="Journal" count={d.length} />
            {d.map((b) => <BuchungRow key={b.id} b={b} />)}
          </>
        )
      ) : tab === 'rechnungen' && d ? (
        d.length === 0 ? (
          <Leer>Keine versendeten Rechnungen für {jahr}.</Leer>
        ) : (
          <>
            <SectionHead label="Rechnungen" count={d.length} />
            {d.map((r) => (
              <Row key={r.id} kind={r.status === 'bezahlt' ? 'pos' : r.status === 'storniert' ? 'neg' : 'file'}
                icon={IconReceipt} title={<><span className="tabular-nums">{r.nummer}</span> · {r.empfaenger_name}</>}
                sub={<><span className="tabular-nums">{formatDateDE(r.datum)}</span>{PUNKT}<Zustand ton={r.status === 'bezahlt' ? 'pos' : r.status === 'storniert' ? 'neg' : 'leise'}>{STATUS[r.status] || r.status}</Zustand></>}
                amount={formatEuro(r.summe_cent)}
                actions={<IconButton icon={IconFileText} label="PDF ansehen" onClick={() => pdfOeffnen(r.id)} />} />
            ))}
          </>
        )
      ) : tab === 'anlagen' && d ? (
        d.length === 0 ? (
          <Leer>Keine Anschaffungen erfasst.</Leer>
        ) : (
          <>
            <SectionHead label="Abschreibungen" count={d.length} />
            {d.map((a) => (
              <Row key={a.id} kind="out" icon={IconTrendDown} title={a.bezeichnung}
                sub={<><span className="tabular-nums">{formatDateDE(a.anschaffungsdatum)}</span>{PUNKT}<span>{a.methode_text}</span>{PUNKT}<span className="tabular-nums">Restbuchwert {formatEuro(a.restbuchwert_cent)}</span></>}
                amount={formatEuro(a.jahres_afa_cent ?? 0)}
                children={<div className="text-[13px] text-ink/60">Anschaffungskosten {formatEuro(a.anschaffungskosten_cent)} · AfA {jahr}</div>} />
            ))}
          </>
        )
      ) : null}
    </div>
  );
}

function BuchungRow({ b }) {
  const [belege, setBelege] = useState(null);
  const typen = new Set(b.positionen.map((p) => p.kategorie_typ));
  const typ = typen.size === 1 ? [...typen][0] : null;
  const einzel = b.positionen.length === 1;
  async function zeigen() {
    try {
      const res = await api.get(`/api/buchungen/${b.id}/belege`);
      if (res.data.length === 1) return openBeleg(res.data[0].id);
      setBelege(res.data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }
  return (
    <Row kind={typ === 'einnahme' ? 'in' : 'out'} icon={typ === 'einnahme' ? IconArrowIn : IconArrowOut}
      title={b.beschreibung || (einzel ? b.positionen[0].kategorie_name : `${b.positionen.length} Positionen`)} wrapTitle
      sub={<>
        <span className="tabular-nums">{formatDateDE(b.datum)}</span>
        {PUNKT}
        <span>{einzel ? b.positionen[0].kategorie_name : b.positionen.map((p) => `${p.kategorie_name} ${formatEuro(p.betrag_cent)}`).join(' · ')}</span>
        {b.beleg_count > 0 && <>{PUNKT}<button type="button" className="font-bold text-royal hover:underline" onClick={zeigen}>{b.beleg_count === 1 ? 'Beleg ansehen' : `${b.beleg_count} Belege`}</button></>}
      </>}
      amount={`${typ ? (typ === 'einnahme' ? '+' : '−') : ''}${formatEuro(b.summe_cent)}`} amountIn={typ === 'einnahme'}>
      {belege && (
        <div className="mt-1 flex flex-wrap gap-2">
          {belege.map((x) => (
            <button key={x.id} type="button" className="btn-outline btn-sm" onClick={() => openBeleg(x.id)}>{x.original_name}</button>
          ))}
        </div>
      )}
    </Row>
  );
}
