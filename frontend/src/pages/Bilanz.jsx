import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Dropdown from '../components/Dropdown.jsx';
import { IconButton, IconDownload, IconPlus, IconPrinter, IconTrash } from '../components/Icons.jsx';
import { Hinweis, KeinGewerbe, Kennzahl, Kennzahlen, Leer, PageHeader, SectionHead } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { centToInput, formatDateDE, formatEuro, parseEuroToCent } from '../lib/format.js';
import { istBilanz } from '../lib/gewinnermittlung.js';

// Bilanz und GuV als Entwurf für die Steuerberatung (BILANZ.md). Gerechnet wird nur auf dem Server
// (services/bilanz.py, abgeleitetes Journal); hier nur Anzeige, Eröffnungswerte und Abschlussbuchungen.

const REITER = [
  { key: 'bilanz', label: 'Bilanz' },
  { key: 'guv', label: 'GuV' },
  { key: 'abstimmung', label: 'Abstimmung' },
  { key: 'eroeffnung', label: 'Eröffnung' },
  { key: 'abschluss', label: 'Abschlussbuchungen' },
  { key: 'journal', label: 'Journal' },
];

// Häufige Abschlussbuchungen als Vorlage (Soll an Haben)
const VORLAGEN = [
  { label: 'Rückstellung bilden', soll: 'guv:sonstige_aufwendungen', haben: 'rueckstellungen', text: 'Rückstellung Jahresabschluss' },
  { label: 'Rückstellung auflösen', soll: 'rueckstellungen', haben: 'guv:sonstige_ertraege', text: 'Auflösung Rückstellung' },
  { label: 'Bar bezahlt', soll: 'verrechnung', haben: 'kasse', text: 'Bar bezahlt' },
  { label: 'Privat bezahlt', soll: 'verrechnung', haben: 'privat', text: 'Privat bezahlt (Einlage)' },
  { label: 'Vorauszahlung abgrenzen', soll: 'ara', haben: 'guv:sonstige_aufwendungen', text: 'Aktive Rechnungsabgrenzung' },
  { label: 'Verbindlichkeit aus Eröffnung bezahlt', soll: 'verbindlichkeiten', haben: 'verrechnung', text: 'Verbindlichkeit Vorjahr bezahlt' },
];

const TON = { ok: 'info', leise: 'info', warn: 'warn', neg: 'neg' };

function Betrag({ cent, className = '' }) {
  return <span className={`whitespace-nowrap tabular-nums ${cent < 0 ? 'text-[#c0392b]' : ''} ${className}`}>{formatEuro(cent)}</span>;
}

function Seite({ titel, posten, summe }) {
  return (
    <section>
      <div className="eyebrow mb-1">{titel}</div>
      <table className="w-full text-[13.5px]">
        <tbody className="divide-y divide-ink/[0.06]">
          {posten.map((p) => (
            <tr key={p.key} className="align-top">
              <td className="py-2 pr-2">
                <div className={p.betrag_cent ? 'font-bold' : 'text-ink/60'}>{p.name}</div>
                {p.konten.length > 0 && (p.konten.length > 1 || p.konten[0].name !== p.name) && (
                  <ul className="mt-0.5 space-y-0.5 text-xs text-ink/60">
                    {p.konten.map((k) => (
                      <li key={k.konto} className="flex justify-between gap-3">
                        <span>{k.name}</span>
                        <Betrag cent={k.betrag_cent} />
                      </li>
                    ))}
                  </ul>
                )}
              </td>
              <td className="py-2 pl-3 text-right font-bold">
                <Betrag cent={p.betrag_cent} />
              </td>
            </tr>
          ))}
          <tr className="border-t-2 border-ink/20">
            <td className="py-2 font-black">Summe</td>
            <td className="py-2 pl-3 text-right font-black">
              <Betrag cent={summe} />
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}

function GuV({ d }) {
  return (
    <table className="mt-2 w-full text-[13.5px]">
      <tbody className="divide-y divide-ink/[0.06]">
        {d.guv.map((p) => (
          <tr key={p.key} className={p.betrag_cent ? '' : 'text-ink/45'}>
            <td className="w-12 py-1.5 font-mono tabular-nums">{p.nr}</td>
            <td className="py-1.5">{p.name}</td>
            <td className="py-1.5 pl-3 text-right">
              <Betrag cent={p.ertrag ? p.betrag_cent : -p.betrag_cent} />
            </td>
          </tr>
        ))}
        <tr className="border-t-2 border-ink/20 font-black">
          <td className="py-2 font-mono">17.</td>
          <td className="py-2">{d.ergebnis_cent >= 0 ? 'Jahresüberschuss' : 'Jahresfehlbetrag'}</td>
          <td className="py-2 pl-3 text-right">
            <Betrag cent={d.ergebnis_cent} />
          </td>
        </tr>
        {d.hinzurechnungen.map((h) => (
          <tr key={h.text} className="text-ink/70">
            <td />
            <td className="py-1.5">+ außerbilanziell: {h.text}</td>
            <td className="py-1.5 pl-3 text-right">
              <Betrag cent={h.betrag_cent} />
            </td>
          </tr>
        ))}
        {d.hinzurechnungen.length > 0 && (
          <tr className="font-bold">
            <td />
            <td className="py-2">Steuerlicher Gewinn (vor weiteren Korrekturen)</td>
            <td className="py-2 pl-3 text-right">
              <Betrag cent={d.steuerlicher_gewinn_cent} />
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}

function Eroeffnung({ d, gewerbeId, jahr, onSaved }) {
  const e = d.eroeffnung;
  const start = useMemo(() => Object.fromEntries(e.werte.map((w) => [w.posten, centToInput(w.betrag_cent)])), [e.werte]);
  const [werte, setWerte] = useState(start);
  const [busy, setBusy] = useState(false);
  useEffect(() => setWerte(start), [start]);

  if (!e.manuell) {
    return (
      <div>
        <p className="mt-2 text-[13.5px] text-ink/80">
          Die Eröffnung {jahr} ist der Schlussbestand {jahr - 1} (Bilanzidentität) und lässt sich nicht von Hand ändern.
        </p>
        <table className="mt-3 w-full text-[13.5px]">
          <tbody className="divide-y divide-ink/[0.06]">
            {e.salden.map((s) => (
              <tr key={s.konto}>
                <td className="py-1.5">{s.name}</td>
                <td className="py-1.5 pl-3 text-right">
                  <Betrag cent={s.saldo_cent > 0 ? s.saldo_cent : -s.saldo_cent} />
                  <span className="ml-1 text-xs text-ink/45">{s.saldo_cent > 0 ? 'Aktiv' : 'Passiv'}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  const cent = (k) => parseEuroToCent(werte[k] || '') || 0;
  const aktiv = e.posten_aktiv.reduce((s, p) => s + cent(p.posten), 0);
  const passiv = e.posten_passiv.reduce((s, p) => s + cent(p.posten), 0);
  const v = e.vorschlag;

  async function speichern() {
    const liste = [...e.posten_aktiv, ...e.posten_passiv].map((p) => {
      const roh = (werte[p.posten] || '').trim();
      const c = roh ? parseEuroToCent(roh) : 0;
      return { posten: p.posten, betrag_cent: c, roh };
    });
    const falsch = liste.find((x) => x.roh && (x.betrag_cent === null || x.betrag_cent < 0));
    if (falsch) return toast.error('Bitte nur positive Beträge eintragen.');
    setBusy(true);
    try {
      await api.put('/api/bilanz/eroeffnung', {
        gewerbe_id: Number(gewerbeId),
        jahr,
        werte: liste.filter((x) => x.betrag_cent > 0).map(({ posten, betrag_cent }) => ({ posten, betrag_cent })),
      });
      toast.success('Eröffnungswerte gespeichert.');
      onSaved();
    } catch (err) {
      toast.error(apiError(err), { duration: 8000 });
    } finally {
      setBusy(false);
    }
  }

  const feld = (p, vorschlag) => (
    <label key={p.posten} className="grid grid-cols-[minmax(0,1fr)_9rem] items-center gap-3 py-1">
      <span className="text-[13.5px]">
        {p.name}
        {vorschlag !== undefined && vorschlag > 0 && (
          <button
            type="button"
            className="ml-2 text-xs text-royal underline"
            onClick={() => setWerte((w) => ({ ...w, [p.posten]: centToInput(vorschlag) }))}
          >
            Vorschlag {formatEuro(vorschlag)}
          </button>
        )}
      </span>
      <input
        className="input text-right tabular-nums"
        inputMode="decimal"
        placeholder="0,00"
        value={werte[p.posten] || ''}
        onChange={(ev) => setWerte((w) => ({ ...w, [p.posten]: ev.target.value }))}
      />
    </label>
  );

  return (
    <div className="max-w-2xl">
      <p className="mt-2 text-[13.5px] leading-snug text-ink/80">
        Erstes Bilanz-Jahr: Trag die Werte zum 31.12.{jahr - 1} ein — Kontostände vom Auszug, Bargeld, offene Rechnungen
        (an dich und von dir), sonstige Posten. Das Eigenkapital ergibt sich daraus.
      </p>
      <SectionHead label="Aktiva" />
      {e.posten_aktiv.map((p) =>
        feld(p, p.posten === 'anlage' ? v?.anlage_cent : p.posten === 'forderungen' ? v?.forderungen_cent : undefined),
      )}
      <SectionHead label="Passiva (ohne Eigenkapital)" />
      {e.posten_passiv.map((p) => feld(p))}
      <div className="mt-3 flex items-center justify-between border-t border-ink/[0.08] pt-3 text-[13.5px] font-bold">
        <span>Eigenkapital zum 1.1.{jahr}</span>
        <Betrag cent={aktiv - passiv} />
      </div>
      {v && (v.anlagen.length > 0 || v.rechnungen.length > 0) && (
        <Hinweis className="mt-3" titel="Woher die Vorschläge kommen">
          {v.anlagen.length > 0 && <>Anlagen: Buchwerte laut AfA-Plan ({v.anlagen.map((a) => a.bezeichnung).join(', ')}). </>}
          {v.rechnungen.length > 0 && <>Forderungen: offene Rechnungen {v.rechnungen.map((r) => r.nummer).join(', ')}. </>}
          Kontostände kennt Tab nicht — bitte vom Kontoauszug zum 31.12. abschreiben.
        </Hinweis>
      )}
      <div className="mt-4">
        <button type="button" className="btn-primary" disabled={busy} onClick={speichern}>
          Eröffnung speichern
        </button>
      </div>
    </div>
  );
}

function Abschluss({ d, gewerbeId, jahr, onSaved }) {
  const leer = { datum: `${jahr}-12-31`, soll: 'guv:sonstige_aufwendungen', haben: 'rueckstellungen', betrag: '', text: '' };
  const [f, setF] = useState(leer);
  const [busy, setBusy] = useState(false);
  const optionen = d.konten.map((k) => ({ value: k.konto, label: k.name }));

  async function anlegen() {
    const c = parseEuroToCent(f.betrag);
    if (!c || c <= 0) return toast.error('Bitte einen Betrag eintragen.');
    setBusy(true);
    try {
      await api.post('/api/bilanz/abschlussbuchungen', {
        gewerbe_id: Number(gewerbeId), datum: f.datum, soll: f.soll, haben: f.haben, betrag_cent: c, text: f.text || null,
      });
      setF(leer);
      onSaved();
    } catch (err) {
      toast.error(apiError(err), { duration: 8000 });
    } finally {
      setBusy(false);
    }
  }

  async function loeschen(a) {
    if (!window.confirm(`Abschlussbuchung „${a.text || a.soll_name}“ löschen?`)) return;
    try {
      await api.delete(`/api/bilanz/abschlussbuchungen/${a.id}`);
      onSaved();
    } catch (err) {
      toast.error(apiError(err));
    }
  }

  return (
    <div>
      {d.abschlussbuchungen.length === 0 ? (
        <Leer>Noch keine Abschlussbuchungen in {jahr}.</Leer>
      ) : (
        <ul className="mt-2 divide-y divide-ink/[0.06]">
          {d.abschlussbuchungen.map((a) => (
            <li key={a.id} className="flex items-center gap-3 py-2 text-[13.5px]">
              <span className="w-20 shrink-0 tabular-nums text-ink/60">{formatDateDE(a.datum)}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate font-bold">{a.text || 'Abschlussbuchung'}</span>
                <span className="block truncate text-xs text-ink/60">
                  {a.soll_name} an {a.haben_name}
                </span>
              </span>
              <Betrag cent={a.betrag_cent} className="font-bold" />
              <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => loeschen(a)} />
            </li>
          ))}
        </ul>
      )}
      <SectionHead label="Neue Abschlussbuchung" />
      <div className="flex flex-wrap gap-1.5">
        {VORLAGEN.map((v) => (
          <button key={v.label} type="button" className="btn-outline btn-sm" onClick={() => setF((x) => ({ ...x, soll: v.soll, haben: v.haben, text: v.text }))}>
            {v.label}
          </button>
        ))}
      </div>
      <div className="mt-3 grid gap-x-5 gap-y-2 sm:grid-cols-2">
        <div>
          <span className="field-label">Soll</span>
          <Dropdown value={f.soll} onChange={(v) => setF((x) => ({ ...x, soll: String(v) }))} options={optionen} searchable />
        </div>
        <div>
          <span className="field-label">Haben</span>
          <Dropdown value={f.haben} onChange={(v) => setF((x) => ({ ...x, haben: String(v) }))} options={optionen} searchable />
        </div>
        <label className="block">
          <span className="field-label">Datum</span>
          <input type="date" className="input" value={f.datum} onChange={(e) => setF((x) => ({ ...x, datum: e.target.value }))} />
        </label>
        <label className="block">
          <span className="field-label">Betrag</span>
          <input className="input tabular-nums" inputMode="decimal" placeholder="0,00" value={f.betrag} onChange={(e) => setF((x) => ({ ...x, betrag: e.target.value }))} />
        </label>
        <label className="block sm:col-span-2">
          <span className="field-label">Text</span>
          <input className="input" maxLength={300} value={f.text} onChange={(e) => setF((x) => ({ ...x, text: e.target.value }))} />
        </label>
      </div>
      <div className="mt-3">
        <button type="button" className="btn-primary" disabled={busy} onClick={anlegen}>
          <IconPlus className="h-4 w-4" /> Buchen
        </button>
      </div>
      <Hinweis className="mt-4">
        Abschlussbuchungen sind für das, was Tab nicht aus Buchungen, Rechnungen und Bank kennt: Rückstellungen,
        Rechnungsabgrenzung, Kasse, bar oder privat Bezahltes. Eine Rückstellung löst du im Folgejahr auf, wenn die
        Rechnung kommt. Welche Abschlussbuchungen nötig sind, entscheidet die Steuerberatung.
      </Hinweis>
    </div>
  );
}

function Journal({ gewerbeId, jahr }) {
  const [zeilen, setZeilen] = useState(null);
  useEffect(() => {
    api
      .get('/api/bilanz/journal', { params: { gewerbe_id: gewerbeId, jahr } })
      .then((r) => setZeilen(r.data))
      .catch((e) => toast.error(apiError(e)));
  }, [gewerbeId, jahr]);
  if (!zeilen) return <PageSpinner />;
  if (!zeilen.length) return <Leer>Keine Buchungen im Jahr.</Leer>;
  return (
    <div className="mt-2 overflow-x-auto">
      <table className="w-full min-w-[640px] text-[13px]">
        <thead>
          <tr className="text-left text-[11px] font-bold uppercase tracking-[0.08em] text-ink/60">
            <th className="py-1 font-bold">Datum</th>
            <th className="py-1 font-bold">Soll</th>
            <th className="py-1 font-bold">Haben</th>
            <th className="py-1 font-bold">Text</th>
            <th className="py-1 text-right font-bold">Betrag</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-ink/[0.06]">
          {zeilen.map((z, i) => (
            <tr key={i}>
              <td className="whitespace-nowrap py-1 pr-2 tabular-nums">{formatDateDE(z.datum)}</td>
              <td className="py-1 pr-2">{z.soll_name}</td>
              <td className="py-1 pr-2">{z.haben_name}</td>
              <td className="py-1 pr-2 text-ink/70">
                {z.text}
                {z.ref && <span className="ml-1 font-mono text-[11px] text-ink/45">{z.ref}</span>}
              </td>
              <td className="py-1 text-right">
                <Betrag cent={z.betrag_cent} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function Bilanz() {
  const { gewerbeId, jahr, gewerbe } = useOutletContext();
  const g = gewerbe.find((x) => String(x.id) === String(gewerbeId));
  const bilanzJahr = istBilanz(g, jahr);
  const [d, setD] = useState(null);
  const [laedt, setLaedt] = useState(false);
  const [reiter, setReiter] = useState('bilanz');

  const laden = useCallback(async () => {
    if (!gewerbeId || !bilanzJahr) return;
    setLaedt(true);
    try {
      const r = await api.get('/api/bilanz', { params: { gewerbe_id: gewerbeId, jahr } });
      setD(r.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLaedt(false);
    }
  }, [gewerbeId, jahr, bilanzJahr]);

  useEffect(() => {
    setD(null);
    laden();
  }, [laden]);

  async function csv() {
    try {
      const res = await api.get('/api/bilanz/bilanz.csv', { params: { gewerbe_id: gewerbeId, jahr }, responseType: 'blob' });
      const href = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = href;
      a.download = `bilanz-${jahr}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(href);
    } catch (e) {
      toast.error(apiError(e, 'Download fehlgeschlagen.'));
    }
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (!bilanzJahr) {
    return (
      <div className="space-y-4">
        <PageHeader title="Bilanz" accent={jahr} sub={g?.name} />
        <Leer>
          {g?.name || 'Dieses Gewerbe'} ermittelt den Gewinn {jahr} per Einnahmen-Überschuss-Rechnung. Umstellen lässt sich
          das unter <Link to="/gewerbe" className="text-royal underline">Gewerbe</Link> → Gewinnermittlung.
        </Leer>
      </div>
    );
  }
  if (laedt && !d) return <PageSpinner />;
  if (!d) return null;

  const warnungen = d.abstimmung.filter((a) => a.ton === 'warn' || a.ton === 'neg').length;
  return (
    <div className="print-area">
      <PageHeader title="Bilanz" accent={jahr} sub={`${g?.name ?? ''} · Entwurf für die Steuerberatung`}>
        <IconButton icon={IconDownload} label="Bilanz, GuV und Journal als CSV" onClick={csv} />
        <IconButton icon={IconPrinter} label="Drucken" onClick={() => window.print()} />
      </PageHeader>

      <Kennzahlen cols={3} className="mt-4">
        <Kennzahl label={d.ergebnis_cent >= 0 ? 'Jahresüberschuss' : 'Jahresfehlbetrag'} value={formatEuro(d.ergebnis_cent)} royal />
        <Kennzahl label="Bilanzsumme" value={formatEuro(d.summe_aktiva_cent)} />
        <Kennzahl label="Eigenkapital 31.12." value={formatEuro(d.eigenkapital.ende_cent)} />
      </Kennzahlen>

      {d.uebergangsgewinn_cent !== null && d.uebergangsgewinn_cent !== 0 && (
        <Hinweis className="mt-4" titel={`Übergangs${d.uebergangsgewinn_cent >= 0 ? 'gewinn' : 'verlust'} ${formatEuro(Math.abs(d.uebergangsgewinn_cent))}`}>
          Wechsel von der EÜR zur Bilanz: Forderungen, Verbindlichkeiten und Abgrenzungen der Eröffnung wären sonst nie
          oder doppelt versteuert. Der Betrag gehört nicht in die GuV, sondern wird außerhalb der Bilanz erfasst (auf Antrag
          verteilt auf bis zu drei Jahre, R 4.6 EStR). Bitte mit der Steuerberatung klären.
        </Hinweis>
      )}

      <nav aria-label="Bereiche der Bilanz" className="mt-5 flex gap-1 overflow-x-auto border-b border-ink/[0.08] print:hidden">
        {REITER.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setReiter(t.key)}
            className={`-mb-px inline-flex h-11 shrink-0 items-center gap-1.5 border-b-2 px-3.5 text-[15px] outline-none focus-visible:bg-royal/10 sm:h-10
              ${reiter === t.key ? 'border-royal font-bold text-royal' : 'border-transparent font-medium text-ink/60 hover:text-ink'}`}
          >
            {t.label}
            {t.key === 'abstimmung' && warnungen > 0 && (
              <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-[#b26a00]/[0.12] px-1.5 text-xs font-bold tabular-nums text-[#9a5900]">
                {warnungen}
              </span>
            )}
          </button>
        ))}
      </nav>

      {reiter === 'bilanz' && (
        <div className="mt-4 grid gap-8 lg:grid-cols-2">
          <Seite titel={`Aktiva 31.12.${jahr}`} posten={d.aktiva} summe={d.summe_aktiva_cent} />
          <Seite titel={`Passiva 31.12.${jahr}`} posten={d.passiva} summe={d.summe_passiva_cent} />
        </div>
      )}
      {reiter === 'guv' && <GuV d={d} />}
      {reiter === 'abstimmung' && (
        <div className="mt-3 space-y-2">
          {d.abstimmung.map((a) => (
            <Hinweis key={a.text} ton={TON[a.ton] || 'info'}>
              {a.text}
              {a.ziel && (
                <Link to={a.ziel} className="ml-1 text-royal underline">
                  Ansehen
                </Link>
              )}
            </Hinweis>
          ))}
        </div>
      )}
      {reiter === 'eroeffnung' && <Eroeffnung d={d} gewerbeId={gewerbeId} jahr={jahr} onSaved={laden} />}
      {reiter === 'abschluss' && <Abschluss d={d} gewerbeId={gewerbeId} jahr={jahr} onSaved={laden} />}
      {reiter === 'journal' && <Journal gewerbeId={gewerbeId} jahr={jahr} />}

      <Hinweis className="mt-8" titel="So rechnet Tab">
        Tab leitet die Bilanz aus deinen Buchungen ab: Ausgaben und Einnahmen zählen zum Rechnungsdatum, bis zur Zahlung
        stehen sie als Verbindlichkeit bzw. Forderung in der Bilanz. Tab-Rechnungen zählen zum Rechnungsdatum, Anlagen mit
        ihrem Buchwert, Bankkonten mit Eröffnungsstand plus Umsätzen. Was Tab keinem Posten zuordnen kann, steht auf dem
        Verrechnungskonto — die Abstimmung sagt, woran es liegt. Das ist ein Entwurf: Jahresabschluss, E-Bilanz und
        Steuererklärung macht die Steuerberatung. Nicht abgedeckt: Inventur und Warenbestand, § 7g, Rücklagen, latente
        Steuern, Anhang.
      </Hinweis>
    </div>
  );
}
