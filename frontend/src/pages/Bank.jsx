import { useEffect, useRef, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import BuchungModal from '../components/BuchungModal.jsx';
import { DialogFuss, Gruppe } from '../components/DialogParts.jsx';
import Dropdown from '../components/Dropdown.jsx';
import { IconArrowIn, IconArrowOut, IconBank, IconUpload } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import { Hinweis, KeinGewerbe, Kennzahl, Kennzahlen, Leer, PageHeader, PUNKT, Row, Zustand } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatDateDE, formatEuro } from '../lib/format.js';

// Bank (Aufbau nach Haben): Kontoauszug als CAMT.053 oder CSV importieren, jeden Umsatz einer
// Buchung zuordnen, ignorieren oder offen lassen. Kein Bankabruf — die Datei kommt von dir.
// Zugeordnet wird im normalen Buchungs-Fenster, vorbelegt aus dem Umsatz.

const FILTER = [
  ['offen', 'Offen'],
  ['alle', 'Alle'],
  ['zugeordnet', 'Zugeordnet'],
  ['ignoriert', 'Ignoriert'],
];
const IGNORIER_GRUENDE = ['Privat', 'Umbuchung zwischen eigenen Konten', 'Nicht betrieblich', 'Sonstiges'];

export default function Bank() {
  const { gewerbeId, reloadBadges } = useOutletContext();
  const [konten, setKonten] = useState([]);
  const [konto, setKonto] = useState('');
  const [filter, setFilter] = useState('offen');
  const [q, setQ] = useState('');
  const [daten, setDaten] = useState(null);
  const [importDatei, setImportDatei] = useState(null);
  const [umsatz, setUmsatz] = useState(null);
  const [buchen, setBuchen] = useState(null);
  const dateiRef = useRef(null);

  async function load() {
    if (!gewerbeId) return;
    try {
      const [k, u] = await Promise.all([
        api.get('/api/bank/konten', { params: { gewerbe_id: gewerbeId } }),
        api.get('/api/bank/umsaetze', {
          params: { gewerbe_id: gewerbeId, filter, ...(konto ? { konto_id: konto } : {}), ...(q.trim() ? { q: q.trim() } : {}) },
        }),
      ]);
      setKonten(k.data);
      setDaten(u.data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  useEffect(() => {
    const t = setTimeout(load, q ? 250 : 0);
    return () => clearTimeout(t);
  }, [gewerbeId, konto, filter, q]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setKonto('');
    setDaten(null);
  }, [gewerbeId]);

  async function nachAenderung() {
    await load();
    reloadBadges?.();
  }

  // Zuordnen: Buchungs-Fenster vorbelegt öffnen (Kategorien des Umsatzjahres nachladen).
  async function starteBuchen(p) {
    const jahrU = Number(p.datum.slice(0, 4));
    try {
      const [kat, bel] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr: jahrU } }),
        p.belegId ? api.get('/api/belege', { params: { gewerbe_id: gewerbeId, status: 'offen' } }) : Promise.resolve(null),
      ]);
      let kategorieId = p.kategorieId;
      if (p.rechnung) {
        const key = p.rechnung.steuerhinweis === 'vers4nr11' ? 'einnahme_steuerfrei' : 'einnahme_ku';
        kategorieId = kat.data.find((k) => k.key === key)?.id ?? kategorieId;
      }
      const beleg = bel?.data.find((b) => b.id === p.belegId);
      setUmsatz(null);
      setBuchen({ ...p, jahr: jahrU, kategorien: kat.data, kategorieId, preBelege: beleg ? [beleg] : [] });
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (!daten) return <PageSpinner />;

  const offenGesamt = konten.reduce((s, k) => s + k.offen, 0);

  return (
    <div>
      <PageHeader
        title="Bank"
        sub="Kontoauszug importieren und jeden Umsatz einer Buchung zuordnen — Tab ruft dein Konto nicht ab, die Datei kommt von dir."
      >
        <input
          ref={dateiRef}
          type="file"
          accept=".csv,.xml,.txt,.camt,text/csv,text/xml,application/xml"
          className="hidden"
          onChange={(e) => {
            if (e.target.files?.[0]) setImportDatei(e.target.files[0]);
            e.target.value = '';
          }}
        />
        <button className="btn-primary" onClick={() => dateiRef.current?.click()}>
          <IconUpload className="mr-1 h-4 w-4" /> Kontoauszug
        </button>
      </PageHeader>

      {konten.length === 0 ? (
        <Leer>
          Noch kein Konto. Exportiere bei deiner Bank die Umsätze als <strong>CAMT.053</strong> (XML) oder CSV und
          importiere die Datei mit „Kontoauszug“. Nennt die Datei die IBAN, legt Tab das Konto selbst an.
        </Leer>
      ) : (
        <>
          {konten.length > 1 && (
            <div className="mt-5 flex flex-wrap gap-2" role="group" aria-label="Konten">
              <button className={`${konto === '' ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setKonto('')}>
                Alle Konten{offenGesamt ? ` · ${offenGesamt}` : ''}
              </button>
              {konten.map((k) => (
                <button
                  key={k.id}
                  className={`${String(konto) === String(k.id) ? 'btn-primary' : 'btn-outline'} btn-sm`}
                  onClick={() => setKonto(String(k.id))}
                >
                  {k.name}
                  {k.offen ? ` · ${k.offen}` : ''}
                </button>
              ))}
            </div>
          )}

          <Kennzahlen cols={3} className="mt-5">
            <Kennzahl label="Offene Umsätze" value={daten.offen.anzahl} />
            <Kennzahl label="Offene Eingänge" value={formatEuro(daten.offen.eingaenge_cent)} royal />
            <Kennzahl label="Offene Ausgänge" value={formatEuro(daten.offen.ausgaenge_cent)} />
          </Kennzahlen>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter">
              {FILTER.map(([wert, label]) => (
                <button key={wert} className={`${filter === wert ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setFilter(wert)}>
                  {label}
                  {wert === 'offen' ? ` · ${daten.offen.anzahl}` : ''}
                </button>
              ))}
            </div>
            <input
              className="input !w-auto min-w-[12rem] flex-1 sm:max-w-xs"
              placeholder="Suchen (Gegenpartei, Zweck, Betrag)…"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              aria-label="Umsätze durchsuchen"
            />
          </div>

          <div className="mt-2">
            {daten.umsaetze.length === 0 ? (
              <Leer>{filter === 'offen' && !q ? 'Alles zugeordnet.' : 'Keine Umsätze.'}</Leer>
            ) : (
              daten.umsaetze.map((u) => (
                <UmsatzZeile key={u.id} u={u} onOeffnen={() => setUmsatz(u)} />
              ))
            )}
          </div>
        </>
      )}

      {importDatei && (
        <ImportModal
          datei={importDatei}
          gewerbeId={gewerbeId}
          konten={konten}
          onClose={() => setImportDatei(null)}
          onDone={async (res) => {
            if (res?.konto_id) setKonto('');
            setFilter('offen');
            await nachAenderung();
          }}
        />
      )}
      {umsatz && (
        <UmsatzModal
          umsatz={umsatz}
          konten={konten}
          onClose={() => setUmsatz(null)}
          onBuchen={starteBuchen}
          onChanged={async () => {
            setUmsatz(null);
            await nachAenderung();
          }}
        />
      )}
      {buchen && (
        <BuchungModal
          gewerbeId={gewerbeId}
          jahr={buchen.jahr}
          kategorien={buchen.kategorien}
          presetKategorieId={buchen.kategorieId}
          presetBetragCent={buchen.betragCent}
          presetBeschreibung={buchen.beschreibung}
          presetDatum={buchen.datum}
          presetRichtung={buchen.richtung}
          rechnungId={buchen.rechnung?.id}
          umsatzId={buchen.umsatzId}
          preBelege={buchen.preBelege}
          onClose={() => setBuchen(null)}
          onSaved={nachAenderung}
        />
      )}
    </div>
  );
}

function UmsatzZeile({ u, onOeffnen }) {
  const eingang = u.betrag_cent > 0;
  const status = u.status_effektiv;
  return (
    <Row
      kind={eingang ? 'in' : 'out'}
      icon={eingang ? IconArrowIn : IconArrowOut}
      muted={status === 'ignoriert'}
      title={u.gegenpartei || u.verwendungszweck || '–'}
      sub={
        <>
          {status === 'offen' ? (
            u.rechnung_hinweis ? (
              <Zustand ton="royal">Vorschlag: Rechnung {u.rechnung_hinweis.nummer}</Zustand>
            ) : (
              <Zustand ton="warn">Offen</Zustand>
            )
          ) : status === 'zugeordnet' ? (
            <Zustand ton="pos">Gebucht</Zustand>
          ) : (
            <Zustand>Ignoriert{u.ignoriert_grund ? ` · ${u.ignoriert_grund}` : ''}</Zustand>
          )}
          {PUNKT}
          <span className="tabular-nums">{formatDateDE(u.datum)}</span>
        </>
      }
      amount={formatEuro(u.betrag_cent)}
      amountIn={eingang}
      actionsClass="sm:w-[7rem]"
      actions={
        status === 'offen' ? (
          <button className="btn-primary btn-sm w-full sm:w-auto" onClick={onOeffnen}>
            Zuordnen
          </button>
        ) : (
          <button className="btn-outline btn-sm w-full sm:w-auto" onClick={onOeffnen}>
            Details
          </button>
        )
      }
    >
      {u.gegenpartei && u.verwendungszweck && (
        <p className="mt-0.5 line-clamp-2 break-words text-[13px] leading-snug text-ink/60">{u.verwendungszweck}</p>
      )}
    </Row>
  );
}

// ── Zuordnen ────────────────────────────────────────────────────────────────

function UmsatzModal({ umsatz, konten, onClose, onBuchen, onChanged }) {
  const eingang = umsatz.betrag_cent > 0;
  const betrag = Math.abs(umsatz.betrag_cent);
  const [v, setV] = useState(null);
  const [grund, setGrund] = useState(IGNORIER_GRUENDE[0]);
  const [busy, setBusy] = useState(false);
  const offen = umsatz.status_effektiv === 'offen';
  const kontoName = konten.find((k) => k.id === umsatz.konto_id)?.name;

  useEffect(() => {
    if (!offen) return;
    api
      .get(`/api/bank/umsaetze/${umsatz.id}/vorschlaege`)
      .then((res) => setV(res.data))
      .catch((e) => toast.error(apiError(e)));
  }, [umsatz.id, offen]);

  const basis = {
    umsatzId: umsatz.id,
    datum: umsatz.datum,
    betragCent: betrag,
    richtung: eingang ? 'einnahme' : 'ausgabe',
  };
  const beschreibungAusgang = [umsatz.gegenpartei, umsatz.verwendungszweck].filter(Boolean).join(' – ').slice(0, 120);

  async function aufrufen(pfad, body) {
    setBusy(true);
    try {
      await api.post(`/api/bank/umsaetze/${umsatz.id}/${pfad}`, body);
      toast.success(pfad === 'ignorieren' ? 'Ignoriert.' : 'Wieder offen.');
      await onChanged();
    } catch (e) {
      toast.error(apiError(e));
      setBusy(false);
    }
  }

  const rechnungWaehlen = (r) =>
    onBuchen({
      ...basis,
      beschreibung: `Rechnung ${r.nummer} – ${r.empfaenger_name}`,
      rechnung: r,
    });

  return (
    <Modal
      title={formatEuro(umsatz.betrag_cent)}
      subtitle={`${umsatz.gegenpartei || 'Umsatz'} · ${formatDateDE(umsatz.datum)}${kontoName ? ` · ${kontoName}` : ''}`}
      onClose={onClose}
      maxWidth="max-w-xl"
    >
      <div className="space-y-4">
        <dl className="space-y-1 text-[13px] leading-snug">
          {umsatz.verwendungszweck && <Zeile label="Verwendungszweck" wert={umsatz.verwendungszweck} />}
          {umsatz.gegenpartei_iban && <Zeile label="IBAN Gegenseite" wert={umsatz.gegenpartei_iban} mono />}
          {umsatz.referenz && <Zeile label="Referenz" wert={umsatz.referenz} mono />}
        </dl>

        {umsatz.status_effektiv === 'zugeordnet' && (
          <>
            <Hinweis>
              Gebucht als Buchung vom {formatDateDE(umsatz.buchung?.datum)}
              {umsatz.buchung?.beschreibung ? `: ${umsatz.buchung.beschreibung}` : ''}. Die Verknüpfung zu lösen lässt die
              Buchung bestehen.
            </Hinweis>
            <DialogFuss>
              <button className="btn-ghost" onClick={onClose}>
                Schließen
              </button>
              <button className="btn-outline" disabled={busy} onClick={() => aufrufen('oeffnen')}>
                Verknüpfung lösen
              </button>
            </DialogFuss>
          </>
        )}

        {umsatz.status_effektiv === 'ignoriert' && (
          <>
            <Hinweis>Ignoriert{umsatz.ignoriert_grund ? `: ${umsatz.ignoriert_grund}` : ''} — zählt nicht als offen.</Hinweis>
            <DialogFuss>
              <button className="btn-ghost" onClick={onClose}>
                Schließen
              </button>
              <button className="btn-outline" disabled={busy} onClick={() => aufrufen('oeffnen')}>
                Wieder öffnen
              </button>
            </DialogFuss>
          </>
        )}

        {offen && !v && <PageSpinner />}
        {offen && v && (
          <>
            {eingang ? (
              <>
                {v.rechnungen.length > 0 && (
                  <Gruppe titel="Bester Treffer">
                    {v.rechnungen.map((r, i) => (
                      <Treffer
                        key={r.id}
                        titel={`${r.nummer} · ${r.empfaenger_name}`}
                        sub={`${formatEuro(r.summe_cent)} · Rechnung vom ${formatDateDE(r.datum)}`}
                        gruende={r.gruende}
                        hinweis={r.summe_cent !== betrag ? `Betrag weicht um ${formatEuro(betrag - r.summe_cent)} ab — gebucht wird der tatsächliche Zahlungseingang, die Rechnung gilt danach als bezahlt.` : null}
                        primaer={i === 0}
                        aktion="Als bezahlt zuordnen"
                        onWaehlen={() => rechnungWaehlen(r)}
                      />
                    ))}
                  </Gruppe>
                )}
                {v.weitere_rechnungen.length > 0 && (
                  <div>
                    <span className="field-label">Andere offene Rechnung</span>
                    <Dropdown
                      value=""
                      searchable
                      placeholder="Rechnung wählen…"
                      options={v.weitere_rechnungen.map((r) => ({
                        value: String(r.id),
                        label: `${r.nummer} · ${r.empfaenger_name} · ${formatEuro(r.summe_cent)}`,
                      }))}
                      onChange={(val) => {
                        const r = v.weitere_rechnungen.find((x) => String(x.id) === String(val));
                        if (r) rechnungWaehlen(r);
                      }}
                    />
                  </div>
                )}
                <button
                  className={v.rechnungen.length ? 'btn-outline' : 'btn-primary'}
                  onClick={() =>
                    onBuchen({ ...basis, beschreibung: beschreibungAusgang, kategorieId: v.kategorie_id })
                  }
                >
                  Ohne Rechnung als Einnahme buchen
                </button>
              </>
            ) : (
              <>
                {v.belege.length > 0 && (
                  <Gruppe titel="Passende Belege im Eingang">
                    {v.belege.map((b, i) => (
                      <Treffer
                        key={b.id}
                        titel={b.original_name}
                        sub={[b.lieferant, b.betrag_cent ? formatEuro(b.betrag_cent) : null, b.datum ? formatDateDE(b.datum) : null]
                          .filter(Boolean)
                          .join(' · ')}
                        gruende={b.gruende}
                        primaer={i === 0}
                        aktion="Mit Beleg buchen"
                        onWaehlen={() =>
                          onBuchen({ ...basis, beschreibung: beschreibungAusgang, kategorieId: v.kategorie_id, belegId: b.id })
                        }
                      />
                    ))}
                  </Gruppe>
                )}
                {v.alle_belege.length > 0 && (
                  <div>
                    <span className="field-label">Beleg aus dem Eingang wählen</span>
                    <Dropdown
                      value=""
                      searchable
                      placeholder="Beleg wählen…"
                      options={v.alle_belege.map((b) => ({
                        value: String(b.id),
                        label: `${b.original_name}${b.faellig_am ? ` · fällig ${formatDateDE(b.faellig_am)}` : ''}`,
                      }))}
                      onChange={(val) =>
                        onBuchen({ ...basis, beschreibung: beschreibungAusgang, kategorieId: v.kategorie_id, belegId: Number(val) })
                      }
                    />
                  </div>
                )}
                <button
                  className={v.belege.length ? 'btn-outline' : 'btn-primary'}
                  onClick={() => onBuchen({ ...basis, beschreibung: beschreibungAusgang, kategorieId: v.kategorie_id })}
                >
                  {v.belege.length ? 'Ohne Beleg buchen' : 'Buchen'}
                </button>
              </>
            )}

            <Gruppe titel="Nicht betrieblich?" className="border-t border-ink/[0.08] pt-4">
              <div className="flex flex-wrap items-end gap-2">
                <div className="min-w-[14rem] flex-1">
                  <Dropdown value={grund} onChange={(x) => setGrund(String(x))} options={IGNORIER_GRUENDE.map((g) => ({ value: g, label: g }))} />
                </div>
                <button className="btn-outline" disabled={busy} onClick={() => aufrufen('ignorieren', { grund })}>
                  Ignorieren
                </button>
              </div>
            </Gruppe>
          </>
        )}
      </div>
    </Modal>
  );
}

function Zeile({ label, wert, mono = false }) {
  return (
    <div className="flex gap-3">
      <dt className="w-32 shrink-0 text-ink/60">{label}</dt>
      <dd className={`min-w-0 break-words ${mono ? 'font-mono text-xs' : ''}`}>{wert}</dd>
    </div>
  );
}

function Treffer({ titel, sub, gruende, hinweis, primaer, aktion, onWaehlen }) {
  return (
    <div className="rounded-xl bg-royal/[0.06] p-3">
      <div className="text-[15px] font-bold leading-snug">{titel}</div>
      {sub && <div className="text-[13px] text-ink/70">{sub}</div>}
      <div className="mt-1 flex flex-wrap gap-1.5">
        {gruende.map((g) => (
          <span key={g} className="rounded-full bg-paper px-2 py-0.5 text-[11px] font-bold text-royal">
            {g}
          </span>
        ))}
      </div>
      {hinweis && <p className="mt-2 text-xs leading-snug text-[#9a5900]">{hinweis}</p>}
      <button className={`${primaer ? 'btn-primary' : 'btn-outline'} btn-sm mt-2.5`} onClick={onWaehlen}>
        {aktion}
      </button>
    </div>
  );
}

// ── Import ──────────────────────────────────────────────────────────────────

const MAPPING_FELDER = [
  ['datum', 'Buchungsdatum'],
  ['betrag', 'Betrag (mit Vorzeichen)'],
  ['soll', 'oder: Soll / Belastung'],
  ['haben', 'oder: Haben / Gutschrift'],
  ['verwendungszweck', 'Verwendungszweck'],
  ['gegenpartei_ein', 'Gegenpartei bei Eingang'],
  ['gegenpartei_aus', 'Gegenpartei bei Ausgang'],
  ['iban', 'IBAN der Gegenseite (optional)'],
];

function ImportModal({ datei, gewerbeId, konten, onClose, onDone }) {
  const [v, setV] = useState(null);
  const [mapping, setMapping] = useState(null);
  const [kontoWahl, setKontoWahl] = useState('datei');
  const [neuName, setNeuName] = useState('');
  const [neuIban, setNeuIban] = useState('');
  const [busy, setBusy] = useState(false);
  const [fehler, setFehler] = useState(null);

  async function vorschau(map) {
    const fd = new FormData();
    fd.append('file', datei);
    fd.append('gewerbe_id', gewerbeId);
    if (map) fd.append('mapping', JSON.stringify(map));
    try {
      const res = await api.post('/api/bank/import/vorschau', fd);
      setV(res.data);
      if (res.data.csv) setMapping(res.data.csv.mapping);
      setFehler(null);
    } catch (e) {
      setFehler(apiError(e, 'Die Datei konnte nicht gelesen werden.'));
    }
  }

  useEffect(() => {
    vorschau(null);
  }, [datei]); // eslint-disable-line react-hooks/exhaustive-deps

  function mappingAendern(feld, wert) {
    const neu = { ...mapping, [feld]: wert === '' ? null : Number(wert) };
    setMapping(neu);
    vorschau(neu);
  }

  async function importieren() {
    setBusy(true);
    try {
      let kontoId = null;
      if (kontoWahl === 'neu') {
        if (!neuName.trim()) {
          toast.error('Bitte dem neuen Konto einen Namen geben.');
          setBusy(false);
          return;
        }
        const k = await api.post('/api/bank/konten', {
          gewerbe_id: Number(gewerbeId),
          name: neuName.trim(),
          iban: neuIban.trim() || null,
        });
        kontoId = k.data.id;
      } else if (kontoWahl !== 'datei') {
        kontoId = Number(kontoWahl);
      }
      const fd = new FormData();
      fd.append('file', datei);
      fd.append('gewerbe_id', gewerbeId);
      if (kontoId) fd.append('konto_id', kontoId);
      if (mapping) fd.append('mapping', JSON.stringify(mapping));
      const res = await api.post('/api/bank/import', fd);
      const d = res.data;
      toast.success(
        `${d.neu} neue Umsätze für ${d.konto_name}${d.dubletten ? `, ${d.dubletten} schon vorhanden` : ''}.`,
        { duration: 7000 },
      );
      d.warnungen?.forEach((w) => toast(w, { duration: 9000 }));
      if (d.saldo_pruefung && d.saldo_pruefung !== 'ok' && d.saldo_pruefung !== 'unbekannt')
        toast.error(`Saldenprüfung: ${d.saldo_pruefung} — möglicherweise fehlen Umsätze im Auszug.`, { duration: 10000 });
      onClose();
      await onDone(d);
    } catch (e) {
      toast.error(apiError(e));
      setBusy(false);
    }
  }

  const csv = v?.csv;
  const spalten = csv ? [{ value: '', label: '— keine —' }, ...csv.header.map((h, i) => ({ value: String(i), label: h || `Spalte ${i + 1}` }))] : [];
  const bereit = v && !v.fehler && v.anzahl > 0;
  const kontoOptionen = [
    {
      value: 'datei',
      label: !v ? '…' : v.iban ? (v.konto ? `${v.konto.name} (aus der IBAN)` : `Neues Konto aus der IBAN ${v.iban}`) : 'aus der Datei (nennt keine IBAN)',
    },
    ...konten.map((k) => ({ value: String(k.id), label: k.name })),
    { value: 'neu', label: 'Neues Konto anlegen…' },
  ];
  const kannImportieren = bereit && !busy && (kontoWahl !== 'datei' || Boolean(v.iban));

  return (
    <Modal title="Kontoauszug importieren" subtitle={datei.name} onClose={onClose} maxWidth="max-w-2xl">
      <div className="space-y-4">
        {fehler && <Hinweis ton="neg">{fehler}</Hinweis>}
        {!v && !fehler && <PageSpinner />}
        {v && (
          <>
            {v.fehler ? (
              <Hinweis ton="warn" titel="Spalten bitte prüfen">
                {v.fehler}
              </Hinweis>
            ) : (
              <Hinweis>
                <strong>{v.anzahl} Umsätze</strong> vom {formatDateDE(v.von)} bis {formatDateDE(v.bis)} ·{' '}
                {v.format === 'camt053' ? 'CAMT.053' : 'CSV'}
                {v.schon_vorhanden ? ` · ${v.schon_vorhanden} davon schon vorhanden` : ''}
                {v.saldo_pruefung === 'ok' ? ' · Saldo stimmt' : v.saldo_pruefung !== 'unbekannt' ? ` · Saldo ${v.saldo_pruefung}` : ''}
                {v.warnungen?.length ? <span className="mt-1 block text-xs">{v.warnungen.join(' ')}</span> : null}
              </Hinweis>
            )}

            {csv && mapping && (
              <Gruppe titel="Spalten der CSV">
                <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
                  {MAPPING_FELDER.map(([feld, label]) => (
                    <div key={feld} className="block">
                      <span className="field-label">{label}</span>
                      <Dropdown
                        value={mapping[feld] === null || mapping[feld] === undefined ? '' : String(mapping[feld])}
                        onChange={(val) => mappingAendern(feld, val)}
                        options={spalten}
                      />
                    </div>
                  ))}
                </div>
              </Gruppe>
            )}

            {v.beispiele?.length > 0 && (
              <Gruppe titel="So liest Tab die ersten Zeilen">
                <div className="divide-y divide-ink/[0.08] rounded-xl bg-ink/[0.03] text-[13px]">
                  {v.beispiele.map((b, i) => (
                    <div key={i} className="flex items-baseline gap-3 px-3 py-1.5">
                      <span className="w-20 shrink-0 tabular-nums text-ink/60">{formatDateDE(b.datum)}</span>
                      <span className="min-w-0 flex-1 truncate">{b.gegenpartei || b.verwendungszweck || '–'}</span>
                      <span className={`shrink-0 font-bold tabular-nums ${b.betrag_cent > 0 ? 'text-royal' : ''}`}>
                        {formatEuro(b.betrag_cent)}
                      </span>
                    </div>
                  ))}
                </div>
              </Gruppe>
            )}

            <Gruppe titel="Konto">
              <Dropdown value={kontoWahl} onChange={(x) => setKontoWahl(String(x))} options={kontoOptionen} />
              {kontoWahl === 'neu' && (
                <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
                  <label className="block">
                    <span className="field-label">Name des Kontos</span>
                    <input className="input" value={neuName} onChange={(e) => setNeuName(e.target.value)} placeholder="z. B. Geschäftskonto" />
                  </label>
                  <label className="block">
                    <span className="field-label">IBAN (optional)</span>
                    <input className="input" value={neuIban} onChange={(e) => setNeuIban(e.target.value)} placeholder="DE12 …" />
                  </label>
                </div>
              )}
              {kontoWahl === 'datei' && !v.iban && (
                <p className="text-xs text-ink/60">Die Datei nennt keine IBAN — bitte ein Konto wählen oder neu anlegen.</p>
              )}
            </Gruppe>
          </>
        )}
      </div>
      <DialogFuss>
        <button type="button" className="btn-ghost" onClick={onClose}>
          Abbrechen
        </button>
        <button type="button" className="btn-primary" disabled={!kannImportieren} onClick={importieren}>
          {busy ? 'Importiert…' : v?.anzahl ? `${v.anzahl - (v.schon_vorhanden || 0)} neue Umsätze importieren` : 'Importieren'}
        </button>
      </DialogFuss>
    </Modal>
  );
}
