import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { DialogFuss } from '../components/DialogParts.jsx';
import { IconButton, IconFileText, IconLock, IconShieldCheck, IconUnlock } from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import { Hinweis, KeinGewerbe, Leer, PageHeader, PUNKT, Row, SectionHead, Zustand } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatDateDE, formatEuro } from '../lib/format.js';

// Jahresabschluss: Jahr sperren + versiegeln, prüfen, Änderungsprotokoll (Aufbau nach Haben:
// Sperre und Protokoll leben in der Datenbank, die Seite bedient und zeigt sie nur).

const AKTION = { INSERT: 'Angelegt', UPDATE: 'Geändert', DELETE: 'Gelöscht', GENESIS: 'Protokollbeginn' };
const TABELLE = {
  buchung: 'Buchung',
  buchung_position: 'Buchungsposition',
  beleg: 'Beleg',
  afa_buchung: 'AfA-Gut',
  fahrt: 'Fahrt',
  rechnung: 'Rechnung',
  rechnung_position: 'Rechnungsposition',
  mahnung: 'Mahnung',
  gewerbe: 'Gewerbe',
  jahr_abschluss: 'Jahresabschluss',
  system: 'System',
};
const KENNFELDER = ['datum', 'beschreibung', 'bezeichnung', 'nummer', 'empfaenger_name', 'ziel', 'betrag_cent',
  'anschaffungskosten_cent', 'km', 'original_name', 'name', 'jahr', 'abgeschlossen', 'geoeffnet_grund'];

function wert(feld, v) {
  if (v === null || v === undefined || v === '') return '–';
  if (feld.endsWith('_cent')) return formatEuro(v);
  return String(v);
}

function aenderungen(e) {
  let vor = null;
  let nach = null;
  try {
    vor = e.vorher ? JSON.parse(e.vorher) : null;
    nach = e.nachher ? JSON.parse(e.nachher) : null;
  } catch {
    return [];
  }
  if (e.aktion === 'UPDATE' && vor && nach) {
    return Object.keys(nach)
      .filter((k) => k !== 'updated_at' && JSON.stringify(vor[k]) !== JSON.stringify(nach[k]))
      .map((k) => `${k}: ${wert(k, vor[k])} → ${wert(k, nach[k])}`);
  }
  const obj = nach || vor || {};
  if (e.aktion === 'GENESIS') return [obj.hinweis || ''];
  return KENNFELDER.filter((k) => k in obj && obj[k] !== null && obj[k] !== '').map((k) => `${k}: ${wert(k, obj[k])}`);
}

function zeit(ts) {
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' });
}

export default function Abschluss() {
  const { gewerbeId, reloadBadges } = useOutletContext();
  const [daten, setDaten] = useState(null);
  const [schliessen, setSchliessen] = useState(null); // Jahr
  const [oeffnen, setOeffnen] = useState(null); // Jahr
  const [pruefung, setPruefung] = useState(null);
  const [pruefen, setPruefen] = useState(false);
  const [eintraege, setEintraege] = useState([]);
  const [weitere, setWeitere] = useState(false);

  async function load() {
    if (!gewerbeId) return;
    try {
      const [ue, pr] = await Promise.all([
        api.get('/api/abschluss', { params: { gewerbe_id: gewerbeId } }),
        api.get('/api/abschluss/protokoll', { params: { gewerbe_id: gewerbeId, limit: 25 } }),
      ]);
      setDaten(ue.data);
      setEintraege(pr.data.eintraege);
      setWeitere(pr.data.weitere);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  useEffect(() => {
    setDaten(null);
    setPruefung(null);
    load();
  }, [gewerbeId]); // eslint-disable-line react-hooks/exhaustive-deps

  async function mehrLaden() {
    const letzte = eintraege[eintraege.length - 1];
    try {
      const res = await api.get('/api/abschluss/protokoll', {
        params: { gewerbe_id: gewerbeId, limit: 50, vor_id: letzte?.id },
      });
      setEintraege((alt) => [...alt, ...res.data.eintraege]);
      setWeitere(res.data.weitere);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function allePruefen() {
    setPruefen(true);
    try {
      const res = await api.post('/api/abschluss/pruefen', { gewerbe_id: Number(gewerbeId) });
      setPruefung(res.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setPruefen(false);
    }
  }

  async function csv() {
    try {
      const res = await api.get('/api/abschluss/protokoll.csv', { params: { gewerbe_id: gewerbeId }, responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'aenderungsprotokoll.csv';
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (!daten) return <PageSpinner />;

  return (
    <div>
      <PageHeader
        title="Jahresabschluss"
        sub="Ein abgeschlossenes Jahr ist gesperrt: Buchungen, Belege, AfA und Fahrten lassen sich nicht mehr ändern. Jede Änderung steht im Änderungsprotokoll."
      />

      <Hinweis className="mt-5 text-xs">
        Das ist Nachvollziehbarkeit für deine Unterlagen, keine Zertifizierung und keine Steuerberatung. Wer die
        Datenbank direkt ändert, kann die Sperre umgehen — das Siegel und die Hash-Kette machen so etwas sichtbar,
        verhindern es aber nicht. Heb den Prüfwert außerhalb des Servers auf.
      </Hinweis>

      <SectionHead label="Jahre" count={daten.jahre.length} />
      {daten.jahre.length === 0 ? (
        <Leer>Noch keine Jahre mit Daten.</Leer>
      ) : (
        daten.jahre.map((j) => (
          <Row
            key={j.jahr}
            kind={j.abgeschlossen ? 'pos' : 'file'}
            icon={j.abgeschlossen ? IconLock : IconUnlock}
            title={<span className="tabular-nums">{j.jahr}</span>}
            sub={
              <>
                {j.abgeschlossen ? (
                  <Zustand ton="pos">Abgeschlossen {formatDateDE(j.abgeschlossen_am?.slice(0, 10))}</Zustand>
                ) : (
                  <Zustand ton="leise">Offen</Zustand>
                )}
                {PUNKT}
                <span>
                  {j.anzahl_buchungen} Buchung{j.anzahl_buchungen === 1 ? '' : 'en'}
                </span>
                {j.abgeschlossen && j.siegel && (
                  <>
                    {PUNKT}
                    <span className="font-mono text-xs" title={j.siegel}>
                      Siegel {j.siegel.slice(0, 10)}…
                    </span>
                  </>
                )}
                {!j.abgeschlossen && !j.kann_schliessen && (
                  <>
                    {PUNKT}
                    <span>läuft noch</span>
                  </>
                )}
              </>
            }
            actions={
              j.abgeschlossen ? (
                <IconButton icon={IconUnlock} label="Wieder öffnen…" onClick={() => setOeffnen(j.jahr)} />
              ) : (
                <IconButton
                  icon={IconLock}
                  variant={j.kann_schliessen ? 'primary' : 'ghost'}
                  label={j.kann_schliessen ? `${j.jahr} abschließen…` : 'Ein Jahr lässt sich erst nach seinem Ende abschließen'}
                  onClick={() => setSchliessen(j.jahr)}
                  disabled={!j.kann_schliessen}
                />
              )
            }
          >
            {!j.abgeschlossen && j.geoeffnet_am && (
              <p className="mt-0.5 text-[13px] leading-snug text-ink/60">
                Wieder geöffnet am {formatDateDE(j.geoeffnet_am.slice(0, 10))} von {j.geoeffnet_von}: {j.geoeffnet_grund}
              </p>
            )}
          </Row>
        ))
      )}

      <SectionHead label="Prüfen" />
      <p className="max-w-[46rem] text-[13px] leading-snug text-ink/60">
        „Alles prüfen“ rechnet die Hash-Kette des Änderungsprotokolls und das Siegel jedes abgeschlossenen Jahres neu
        und prüft, ob alle Schutz-Trigger der Datenbank vorhanden sind.
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" className="btn-outline" disabled={pruefen} onClick={allePruefen}>
          <IconShieldCheck className="mr-1.5 h-4 w-4" /> {pruefen ? 'Prüft…' : 'Alles prüfen'}
        </button>
        {daten.kopf && (
          <span className="text-xs text-ink/60" title={daten.kopf.hash}>
            Prüfwert: Nr. {daten.kopf.id} · <span className="font-mono">{daten.kopf.hash?.slice(0, 16)}…</span>
          </span>
        )}
      </div>
      {pruefung && (
        <Hinweis ton={pruefung.ok ? 'info' : 'neg'} titel={pruefung.ok ? 'Alles in Ordnung' : 'Abweichungen gefunden'} className="mt-3">
          <ul className="list-disc space-y-0.5 pl-5">
            <li>
              Änderungsprotokoll: {pruefung.kette.eintraege} Einträge,{' '}
              {pruefung.kette.ok ? 'Kette lückenlos und unverändert' : 'Kette gestört'}
            </li>
            {pruefung.kette.fehler.map((f) => (
              <li key={f}>{f}</li>
            ))}
            {pruefung.trigger_fehlen.length > 0 && (
              <li>Schutz-Trigger fehlen oder wurden verändert: {pruefung.trigger_fehlen.join(', ')}</li>
            )}
            {pruefung.jahre.map((j) => (
              <li key={j.jahr}>
                {j.jahr}:{' '}
                {j.ok ? 'Siegel stimmt' : `Siegel passt nicht mehr — verändert: ${j.abweichend.join(', ') || 'unbekannt'}`}
              </li>
            ))}
            {pruefung.jahre.length === 0 && <li>Kein abgeschlossenes Jahr zu prüfen.</li>}
          </ul>
        </Hinweis>
      )}

      <SectionHead label="Änderungsprotokoll" count={eintraege.length + (weitere ? '+' : '')}>
        <button type="button" className="btn-ghost btn-sm" onClick={csv}>
          <IconFileText className="mr-1 h-4 w-4" /> Als CSV laden
        </button>
      </SectionHead>
      {eintraege.length === 0 ? (
        <Leer>Noch keine Einträge für dieses Gewerbe.</Leer>
      ) : (
        eintraege.map((e) => {
          const zeilen = aenderungen(e);
          return (
            <Row
              key={e.id}
              kind={e.aktion === 'DELETE' ? 'neg' : 'out'}
              icon={IconFileText}
              wrapTitle
              title={`${AKTION[e.aktion] || e.aktion} · ${TABELLE[e.tabelle] || e.tabelle} #${e.zeile_id}`}
              sub={
                <>
                  <span className="tabular-nums">{zeit(e.ts)}</span>
                  {PUNKT}
                  <span>{e.actor || 'unbekannt'}</span>
                  {PUNKT}
                  <span className="font-mono text-xs">Nr. {e.id}</span>
                </>
              }
            >
              {zeilen.length > 0 && (
                <p className="mt-0.5 break-words text-[13px] leading-snug text-ink/60">
                  {zeilen.slice(0, 5).join(' · ')}
                  {zeilen.length > 5 ? ' …' : ''}
                </p>
              )}
            </Row>
          );
        })
      )}
      {weitere && (
        <button type="button" className="btn-outline btn-sm mt-3" onClick={mehrLaden}>
          Ältere Einträge laden
        </button>
      )}

      {schliessen && (
        <SchliessenModal
          jahr={schliessen}
          gewerbeId={gewerbeId}
          onClose={() => setSchliessen(null)}
          onDone={async () => {
            await load();
            reloadBadges?.();
          }}
        />
      )}
      {oeffnen && (
        <OeffnenModal
          jahr={oeffnen}
          gewerbeId={gewerbeId}
          onClose={() => setOeffnen(null)}
          onDone={async () => {
            await load();
            reloadBadges?.();
          }}
        />
      )}
    </div>
  );
}

function SchliessenModal({ jahr, gewerbeId, onClose, onDone }) {
  const [busy, setBusy] = useState(false);
  async function los() {
    setBusy(true);
    try {
      await api.post('/api/abschluss/schliessen', { gewerbe_id: Number(gewerbeId), jahr });
      toast.success(`${jahr} abgeschlossen und versiegelt.`);
      onClose();
      await onDone();
    } catch (e) {
      toast.error(apiError(e));
      setBusy(false);
    }
  }
  return (
    <Modal title={`${jahr} abschließen`} onClose={onClose}>
      <div className="space-y-3 text-[15px] leading-snug">
        <p>
          Danach sind <strong>Buchungen, Belege, AfA und Fahrten von {jahr}</strong> gesperrt. Tab versiegelt die Daten
          (SHA-256) und legt das Siegel im Änderungsprotokoll ab.
        </p>
        <Hinweis ton="warn" className="text-sm">
          Lade vorher das Jahresarchiv unter „Export“ herunter und hebe es auf — es enthält den Prüfwert und die
          Prüfsummen. Wieder öffnen geht nur mit Begründung und steht im Protokoll.
        </Hinweis>
      </div>
      <DialogFuss>
        <button type="button" className="btn-ghost" onClick={onClose}>
          Abbrechen
        </button>
        <button type="button" className="btn-primary" disabled={busy} onClick={los}>
          {busy ? 'Versiegelt…' : `${jahr} abschließen`}
        </button>
      </DialogFuss>
    </Modal>
  );
}

function OeffnenModal({ jahr, gewerbeId, onClose, onDone }) {
  const [grund, setGrund] = useState('');
  const [busy, setBusy] = useState(false);
  async function los(e) {
    e.preventDefault();
    setBusy(true);
    try {
      await api.post('/api/abschluss/oeffnen', { gewerbe_id: Number(gewerbeId), jahr, begruendung: grund });
      toast.success(`${jahr} ist wieder offen.`);
      onClose();
      await onDone();
    } catch (err) {
      toast.error(apiError(err));
      setBusy(false);
    }
  }
  return (
    <Modal title={`${jahr} wieder öffnen`} onClose={onClose}>
      <form onSubmit={los} className="space-y-4">
        <p className="text-[15px] leading-snug">
          Ein geöffnetes Jahr ist wieder änderbar. Das Siegel gilt dann nicht mehr; nach dem Schließen entsteht ein
          neues. Begründung und Zeitpunkt stehen im Änderungsprotokoll.
        </p>
        <label className="block">
          <span className="field-label">Begründung (Pflicht)</span>
          <textarea
            className="input min-h-[80px]"
            value={grund}
            maxLength={500}
            autoFocus
            onChange={(e) => setGrund(e.target.value)}
            placeholder="z. B. Änderungsbescheid des Finanzamts, Beleg nachgereicht"
          />
        </label>
        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy || grund.trim().length < 5}>
            Wieder öffnen
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}
