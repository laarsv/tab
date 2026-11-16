import { useCallback, useEffect, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { IconButton, IconCircleCheck, IconDownload, IconList, IconReceipt, IconRepeat } from '../components/Icons.jsx';
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
  Zustand,
} from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatDateDE, formatEuro } from '../lib/format.js';
import { fristInWorten } from '../lib/fristWorte.js';

// Umsatzsteuer-Voranmeldung (nur Regelbesteuerung): Werte für ELSTER je Monat/Quartal, Frist, „übermittelt“.
// Gerechnet wird nur auf dem Server (services/ust_voranmeldung.py); Tab übermittelt nichts.

const ZUSTAND_TEXT = {
  uebermittelt: null,
  kommt: 'Zeitraum hat noch nicht begonnen',
  laeuft: 'Zeitraum läuft',
};

function betragText(cent) {
  if (cent < 0) return `${formatEuro(-cent)} Erstattung`;
  return formatEuro(cent);
}

function euroGanz(eur) {
  return `${Number(eur || 0).toLocaleString('de-DE')} €`;
}

// Kennzahlen wie im ELSTER-Formular: Kz, Bezeichnung, Bemessungsgrundlage (volle Euro), Steuer.
function KennzahlTabelle({ kennzahlen }) {
  return (
    <table className="mt-2 w-full text-[13.5px]">
      <thead>
        <tr className="text-left text-[11px] font-bold uppercase tracking-[0.08em] text-ink/60">
          <th className="w-12 py-1 font-bold">Kz</th>
          <th className="py-1 font-bold">Bezeichnung</th>
          <th className="py-1 pl-4 text-right font-bold">Bemessung</th>
          <th className="py-1 pl-4 text-right font-bold">Steuer</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-ink/[0.06]">
        {kennzahlen.map((k) => (
          <tr key={k.kz} className={k.kz === '83' ? 'font-bold' : ''}>
            <td className="py-1.5 font-mono tabular-nums">{k.kz}</td>
            <td className="py-1.5 pr-2">
              {k.label}
              {k.gebucht_cent !== undefined && k.gebucht_cent !== k.steuer_cent && (
                <span className="block text-xs text-ink/60">
                  gebucht {formatEuro(k.gebucht_cent)} — ELSTER rechnet aus der abgerundeten Bemessungsgrundlage
                </span>
              )}
              {k.steuer_kz && <span className="block text-xs text-ink/60">Steuer in Kz {k.steuer_kz}</span>}
            </td>
            <td className="whitespace-nowrap py-1.5 pl-4 text-right tabular-nums">{k.bemessung_eur !== undefined ? euroGanz(k.bemessung_eur) : ''}</td>
            <td className="whitespace-nowrap py-1.5 pl-4 text-right tabular-nums">{k.steuer_cent !== undefined ? formatEuro(k.steuer_cent) : ''}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Positionen({ gewerbeId, von, bis }) {
  const [daten, setDaten] = useState(null);
  useEffect(() => {
    api
      .get('/api/umsatzsteuer/zeitraum', { params: { gewerbe_id: gewerbeId, von, bis } })
      .then((r) => setDaten(r.data))
      .catch((e) => toast.error(apiError(e)));
  }, [gewerbeId, von, bis]);
  if (!daten) return <p className="mt-2 text-[13px] text-ink/60">Lädt …</p>;
  if (!daten.positionen.length) return <p className="mt-2 text-[13px] text-ink/60">Keine Buchungen in diesem Zeitraum.</p>;
  return (
    <ul className="mt-2 divide-y divide-ink/[0.06] text-[13px]">
      {daten.positionen.map((p, i) => (
        <li key={i} className="flex gap-3 py-1">
          <span className="w-20 shrink-0 tabular-nums text-ink/60">{formatDateDE(p.datum)}</span>
          <span className="min-w-0 flex-1 truncate">
            {p.beschreibung || p.kategorie}
            <span className="text-ink/60"> · {p.kategorie}</span>
          </span>
          <span className="w-12 shrink-0 font-mono text-ink/60">{p.kz ? `Kz ${p.kz}` : '—'}</span>
          <span className="w-24 shrink-0 text-right tabular-nums">{p.steuer_cent ? formatEuro(p.steuer_cent) : ''}</span>
        </li>
      ))}
    </ul>
  );
}

function PeriodeRow({ p, gewerbeId, onUebermittelt }) {
  const [offen, setOffen] = useState(false);
  const frist = fristInWorten(p.frist);
  const faellig = p.status === 'offen' || p.status === 'ueberfaellig';
  const kind = p.status === 'uebermittelt' ? 'pos' : p.status === 'ueberfaellig' ? 'late' : faellig ? 'warn' : 'file';
  return (
    <Row
      kind={kind}
      icon={IconReceipt}
      title={p.label}
      muted={p.status === 'kommt'}
      sub={
        <>
          {p.status === 'uebermittelt' ? (
            <Zustand ton="pos">Übermittelt {formatDateDE(p.uebermittelt_am)}</Zustand>
          ) : ZUSTAND_TEXT[p.status] ? (
            <span>{ZUSTAND_TEXT[p.status]}</span>
          ) : (
            <Zustand ton={p.status === 'ueberfaellig' ? 'late' : 'warn'}>Abgabe {frist.text}</Zustand>
          )}
          {PUNKT}
          <span className="tabular-nums">bis {formatDateDE(p.frist)}</span>
        </>
      }
      amount={betragText(p.kz83_cent)}
      actions={
        <>
          <IconButton icon={IconList} label={offen ? 'Kennzahlen ausblenden' : 'Kennzahlen und Buchungen zeigen'} onClick={() => setOffen(!offen)} />
          {p.status !== 'uebermittelt' && p.status !== 'kommt' && (
            <IconButton icon={IconCircleCheck} variant="primary" label="Als übermittelt markieren" onClick={() => onUebermittelt(p.schluessel, true)} />
          )}
          {p.status === 'uebermittelt' && (
            <IconButton icon={IconRepeat} label="Wieder öffnen" onClick={() => onUebermittelt(p.schluessel, false)} />
          )}
        </>
      }
    >
      {offen && (
        <div className="pb-2">
          <KennzahlTabelle kennzahlen={p.kennzahlen} />
          {p.hinweise.map((h) => (
            <Hinweis key={h} ton="warn" className="mt-2">
              {h}
            </Hinweis>
          ))}
          {(p.gezahlt_cent > 0 || p.erstattet_cent > 0) && (
            <p className="mt-2 text-[13px] text-ink/60">
              Im Zeitraum gebucht: {p.gezahlt_cent > 0 && `${formatEuro(p.gezahlt_cent)} ans Finanzamt gezahlt`}
              {p.gezahlt_cent > 0 && p.erstattet_cent > 0 && ' · '}
              {p.erstattet_cent > 0 && `${formatEuro(p.erstattet_cent)} vom Finanzamt erstattet`} (zählt nicht in die
              Voranmeldung).
            </p>
          )}
          <div className="mt-3 text-[11px] font-bold uppercase tracking-[0.08em] text-ink/60">Buchungen dahinter</div>
          <Positionen gewerbeId={gewerbeId} von={p.von} bis={p.bis} />
        </div>
      )}
    </Row>
  );
}

export default function Umsatzsteuer() {
  const { gewerbeId, jahr, gewerbe } = useOutletContext();
  const [daten, setDaten] = useState(null);
  const [laedt, setLaedt] = useState(true);
  const g = gewerbe.find((x) => String(x.id) === String(gewerbeId));

  const laden = useCallback(async () => {
    if (!gewerbeId) return;
    setLaedt(true);
    try {
      const r = await api.get('/api/umsatzsteuer', { params: { gewerbe_id: gewerbeId, jahr } });
      setDaten(r.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLaedt(false);
    }
  }, [gewerbeId, jahr]);

  useEffect(() => {
    laden();
  }, [laden]);

  async function uebermittelt(schluessel, erledigt) {
    try {
      await api.post('/api/fristen/erledigt', { schluessel, erledigt });
      laden();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function csv() {
    try {
      const res = await api.get('/api/umsatzsteuer/voranmeldungen.csv', { params: { gewerbe_id: gewerbeId, jahr }, responseType: 'blob' });
      const href = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = href;
      a.download = `umsatzsteuer-${jahr}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
    } catch (e) {
      toast.error(apiError(e, 'Download fehlgeschlagen.'));
    }
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (laedt && !daten) return <PageSpinner />;
  if (!daten) return null;

  if (daten.besteuerung !== 'regelbesteuerung') {
    return (
      <div className="space-y-4">
        <PageHeader title="Umsatzsteuer" accent={jahr} sub={g?.name} />
        <Leer>
          {jahr} gilt für {g?.name || 'dieses Gewerbe'} die Kleinunternehmerregelung — es gibt keine
          Umsatzsteuer-Voranmeldung. Umstellen lässt sich das unter <Link to="/gewerbe" className="text-royal underline">Gewerbe</Link> →
          Besteuerung.
        </Leer>
      </div>
    );
  }

  const j = daten.jahr_summe;
  return (
    <div>
      <PageHeader title="Umsatzsteuer" accent={jahr} sub={`${g?.name ?? ''} · Voranmeldung ${daten.zeitraum_label}${daten.dauerfrist ? ', mit Dauerfristverlängerung' : ''}`}>
        <IconButton icon={IconDownload} label="Voranmeldungen als CSV" onClick={csv} />
      </PageHeader>

      <Kennzahlen cols={3} className="mt-4">
        <Kennzahl label="Umsatzsteuer" value={formatEuro(j.umsatzsteuer_cent)} />
        <Kennzahl label="Vorsteuer" value={formatEuro(j.vorsteuer_cent)} />
        <Kennzahl label={j.kz83_cent < 0 ? 'Erstattung' : 'Zahllast'} value={formatEuro(Math.abs(j.kz83_cent))} royal />
      </Kennzahlen>

      {daten.zeitraum === 'jahr' ? (
        <Hinweis className="mt-4">
          Dieses Gewerbe gibt keine Voranmeldungen ab (Einstellung unter <Link to="/gewerbe" className="text-royal underline">Gewerbe</Link>{' '}
          → Besteuerung). Die Werte unten gehören in die Umsatzsteuererklärung.
        </Hinweis>
      ) : (
        <>
          <SectionHead label="Voranmeldungen" count={daten.perioden.length} />
          {daten.perioden.map((p) => (
            <PeriodeRow key={p.key} p={p} gewerbeId={gewerbeId} onUebermittelt={uebermittelt} />
          ))}
        </>
      )}

      <SectionHead label="Umsatzsteuererklärung" />
      <Row
        kind={j.uebermittelt_am ? 'pos' : 'file'}
        icon={IconReceipt}
        title={`Jahr ${jahr}`}
        sub={
          <>
            {j.uebermittelt_am ? (
              <Zustand ton="pos">Übermittelt {formatDateDE(j.uebermittelt_am)}</Zustand>
            ) : (
              <span>Abgabe bis {formatDateDE(j.frist)} ohne Steuerberatung</span>
            )}
            {daten.zeitraum !== 'jahr' && (
              <>
                {PUNKT}
                <span>Summe der Voranmeldungen {betragText(j.summe_voranmeldungen_cent)}</span>
              </>
            )}
          </>
        }
        amount={betragText(j.kz83_cent)}
      >
        <KennzahlTabelle kennzahlen={j.kennzahlen} />
        {j.hinweise.map((h) => (
          <Hinweis key={h} ton="warn" className="mt-2">
            {h}
          </Hinweis>
        ))}
      </Row>

      <Hinweis className="mt-6" titel="So rechnet Tab">
        Ist-Versteuerung: Es zählt der Tag der Zahlung, also das Buchungsdatum — auch für die Vorsteuer (vereinfacht;
        streng genommen zählt bei der Vorsteuer der Rechnungseingang). Bemessungsgrundlagen in vollen Euro, abgerundet.
        Die Jahreswerte können um ein paar Cent von der Summe der Voranmeldungen abweichen, weil jede Voranmeldung für sich
        rundet. Übertragen musst du die Werte selbst in ELSTER; „übermittelt“ ist nur dein Haken. Nicht abgedeckt: § 13b
        (Reverse Charge), innergemeinschaftliche Lieferungen und Erwerbe, Sondervorauszahlung (Kz 39), Vorsteueraufteilung,
        Berichtigungen.
      </Hinweis>
    </div>
  );
}
