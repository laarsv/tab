import { useEffect, useState } from 'react';
import { useNavigate, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { SchalterZeile } from '../components/DialogParts.jsx';
import { IconButton, IconCalendar, IconCircleCheck, IconDownload, IconRepeat } from '../components/Icons.jsx';
import { Hinweis, Leer, PageHeader, PUNKT, Row, SectionHead, Zustand } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { centToInput, formatDateDE, formatEuro, parseEuroToCent } from '../lib/format.js';
import { fristInWorten } from '../lib/fristWorte.js';

// Fristen (Aufbau wie Haben): Überfällig · Nächste 30 Tage · Später · Kalender-Abo · Erledigt.
// Steuertermine für die EÜR — die Frist der Steuererklärung und optional die ESt-Vorauszahlungen.

const KURZ = 6; // „Später“ zeigt erst die nächsten Fristen

function wann(f) {
  return fristInWorten(f.faellig_am).text;
}

function FristRow({ frist, onErledigt }) {
  const navigate = useNavigate();
  const f = frist;
  const dringend = f.status === 'offen' && f.tage_bis <= 7;
  const kind = f.status === 'erledigt' ? 'pos' : f.status === 'ueberfaellig' ? 'late' : f.status === 'hinweis' ? 'out' : dringend ? 'warn' : 'file';
  const ton = f.status === 'ueberfaellig' ? 'late' : dringend ? 'warn' : 'leise';
  return (
    <Row
      kind={kind}
      icon={IconCalendar}
      muted={f.status === 'erledigt'}
      wrapTitle
      title={f.titel}
      sub={
        <>
          {f.status === 'erledigt' ? (
            <Zustand ton="pos">Erledigt {formatDateDE(f.erledigt_am)}</Zustand>
          ) : (
            <Zustand ton={ton}>{wann(f)}</Zustand>
          )}
          {PUNKT}
          <span className="tabular-nums">{formatDateDE(f.faellig_am)}</span>
          {PUNKT}
          <span>{f.art_label}</span>
        </>
      }
      actions={
        <>
          {f.link && f.status !== 'erledigt' && (
            <IconButton icon={IconDownload} label={f.link === '/umsatzsteuer' ? 'Zur Umsatzsteuer' : 'Zum Export (EÜR-Summenblatt)'} onClick={() => navigate(f.link)} />
          )}
          {f.erledigbar && f.status !== 'erledigt' && (
            <IconButton icon={IconCircleCheck} variant="primary" label="Als erledigt markieren" onClick={() => onErledigt(f, true)} />
          )}
          {f.status === 'erledigt' && (
            <IconButton icon={IconRepeat} label="Wieder öffnen" onClick={() => onErledigt(f, false)} />
          )}
        </>
      }
    >
      <p className="mt-0.5 text-[13px] leading-snug text-ink/60">{f.detail}</p>
    </Row>
  );
}

function Gruppe({ label, fristen, onErledigt, leer, kurz = false }) {
  const [alle, setAlle] = useState(false);
  if (fristen.length === 0 && !leer) return null;
  const gezeigt = kurz && !alle ? fristen.slice(0, KURZ) : fristen;
  return (
    <>
      <SectionHead label={label} count={fristen.length} />
      {fristen.length === 0 ? (
        <Leer>{leer}</Leer>
      ) : (
        gezeigt.map((f) => <FristRow key={f.schluessel} frist={f} onErledigt={onErledigt} />)
      )}
      {gezeigt.length < fristen.length && (
        <button type="button" className="btn-outline btn-sm mt-3" onClick={() => setAlle(true)}>
          Alle {fristen.length} zeigen
        </button>
      )}
    </>
  );
}

export default function Fristen() {
  const { reloadBadges } = useOutletContext();
  const [data, setData] = useState(null);
  const [erledigtOffen, setErledigtOffen] = useState(false);

  async function load() {
    try {
      const res = await api.get('/api/fristen');
      setData(res.data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function erledigt(f, wert) {
    try {
      await api.post('/api/fristen/erledigt', { schluessel: f.schluessel, erledigt: wert });
      await load();
      reloadBadges?.();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function vorauszahlung(an) {
    try {
      await api.put('/api/fristen/einstellung', { est_vorauszahlung: an });
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (!data) return <PageSpinner />;

  const items = data.items;
  const offen = items.filter((f) => f.status === 'offen' || f.status === 'hinweis');
  const ueberfaellig = items.filter((f) => f.status === 'ueberfaellig');
  const naechste = offen.filter((f) => f.tage_bis <= data.bald_tage);
  const spaeter = offen.filter((f) => f.tage_bis > data.bald_tage);
  const erledigte = items.filter((f) => f.status === 'erledigt').reverse();

  return (
    <div>
      <PageHeader
        title="Fristen"
        sub="Steuertermine für deine EÜR. Fällt eine Frist auf ein Wochenende oder einen Feiertag, gilt der nächste Werktag."
      />

      <Hinweis className="mt-5 text-xs">
        Tab überträgt nichts ans Finanzamt — hake eine Frist ab, sobald du die Erklärung abgegeben oder die Zahlung
        geleistet hast. Mit Steuerberatung gelten längere Abgabefristen, die kennt Tab nicht. Umsatzsteuer-Termine
        erscheinen nur für Gewerbe mit Regelbesteuerung.
      </Hinweis>

      {items.length === 0 && (
        <Leer>
          Noch keine Fristen. Sobald du für ein Jahr ab 2024 Buchungen oder Rechnungen hast, erscheint hier die
          Abgabefrist deiner Steuererklärung.
        </Leer>
      )}

      <Gruppe label="Überfällig" fristen={ueberfaellig} onErledigt={erledigt} />
      {items.length > 0 && (
        <Gruppe
          label={`Nächste ${data.bald_tage} Tage`}
          fristen={naechste}
          onErledigt={erledigt}
          leer={`In den nächsten ${data.bald_tage} Tagen ist nichts fällig.`}
        />
      )}
      <Gruppe label="Später" fristen={spaeter} onErledigt={erledigt} kurz />

      <Vorauszahlungen onChanged={async () => { await load(); reloadBadges?.(); }} />

      <SectionHead label="Anzeige" />
      <SchalterZeile
        titel="Einkommensteuer-Termine ohne Betrag anzeigen"
        hinweis="10. März, Juni, September und Dezember als Hinweis, für Jahre ohne eingetragene Beträge."
        checked={data.einstellung.est_vorauszahlung}
        onChange={vorauszahlung}
      />

      <KalenderAbo aktiv={data.einstellung.kalender_aktiv} onChanged={load} />

      {erledigte.length > 0 && (
        <>
          <SectionHead label="Erledigt" count={erledigte.length}>
            <button type="button" className="btn-ghost btn-sm" onClick={() => setErledigtOffen((o) => !o)}>
              {erledigtOffen ? 'Ausblenden' : 'Anzeigen'}
            </button>
          </SectionHead>
          {erledigtOffen && erledigte.map((f) => <FristRow key={f.schluessel} frist={f} onErledigt={erledigt} />)}
        </>
      )}
    </div>
  );
}

// Vorauszahlungen laut Bescheid: Betrag je Termin eintragen → abhakbare Fristen mit Betrag (v37).
const VZ_ARTEN = [
  ['est', 'Einkommensteuer', 'Vorauszahlungsbescheid des Finanzamts — Einkommensteuer mit Soli und Kirchensteuer, falls festgesetzt.'],
  ['gewst', 'Gewerbesteuer', 'Vorauszahlungsbescheid der Gemeinde.'],
];

function Vorauszahlungen({ onChanged }) {
  const diesesJahr = new Date().getFullYear();
  const [jahr, setJahr] = useState(diesesJahr);
  const [daten, setDaten] = useState(null);
  const [eingabe, setEingabe] = useState({ est: ['', '', '', ''], gewst: ['', '', '', ''] });
  const [busy, setBusy] = useState(false);

  function uebernehmen(d) {
    setDaten(d);
    setEingabe({
      est: d.arten.est.map((c) => (c ? centToInput(c) : '')),
      gewst: d.arten.gewst.map((c) => (c ? centToInput(c) : '')),
    });
  }

  useEffect(() => {
    api
      .get('/api/fristen/vorauszahlungen', { params: { jahr } })
      .then((r) => uebernehmen(r.data))
      .catch((e) => toast.error(apiError(e)));
  }, [jahr]);

  function setzen(art, q, wert) {
    setEingabe((e) => {
      const neu = [...e[art]];
      neu[q] = wert;
      // Ersten Betrag eintippen füllt leere Quartale mit (Bescheide setzen meist vier gleiche Raten fest)
      if (q === 0 && e[art].slice(1).every((x) => !x || x === e[art][0])) {
        for (let i = 1; i < 4; i++) neu[i] = wert;
      }
      return { ...e, [art]: neu };
    });
  }

  async function speichern(art) {
    const betraege = eingabe[art].map((x) => (String(x).trim() ? parseEuroToCent(x) : null));
    if (betraege.some((b, i) => String(eingabe[art][i]).trim() && (b === null || b < 0))) {
      return toast.error('Bitte Beträge wie 1.234,00 eingeben.');
    }
    setBusy(true);
    try {
      const r = await api.put('/api/fristen/vorauszahlungen', { jahr, art, betraege });
      uebernehmen(r.data);
      toast.success(
        r.data.erkannt
          ? `Gespeichert. ${r.data.erkannt} Zahlung${r.data.erkannt > 1 ? 'en' : ''} auf dem Konto gefunden und abgehakt.`
          : 'Gespeichert.',
      );
      await onChanged();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  const geaendert = (art) =>
    daten && eingabe[art].some((x, i) => (String(x).trim() ? parseEuroToCent(x) : null) !== (daten.arten[art][i] ?? null));

  return (
    <>
      <SectionHead label="Vorauszahlungen">
        <div className="flex gap-1" role="group" aria-label="Jahr">
          {[diesesJahr, diesesJahr + 1].map((j) => (
            <button key={j} type="button" className={`${j === jahr ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setJahr(j)}>
              {j}
            </button>
          ))}
        </div>
      </SectionHead>
      <p className="max-w-[46rem] text-[13px] leading-snug text-ink/60">
        Trag die Beträge aus deinen Bescheiden ein. Jeder Termin erscheint dann oben als Frist mit Betrag, im Zähler, in
        der Übersicht und im Kalender-Abo — abhaken, sobald gezahlt.
      </p>
      {daten &&
        VZ_ARTEN.map(([art, name, hinweis]) => (
          <div key={art} className="mt-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div className="text-[15px] font-bold">
                {name} {jahr}
                {daten.summe_cent[art] > 0 && (
                  <span className="ml-2 font-normal tabular-nums text-ink/60">Jahr: {formatEuro(daten.summe_cent[art])}</span>
                )}
              </div>
              <span className="text-xs text-ink/60">{hinweis}</span>
            </div>
            <div className="mt-1 grid grid-cols-2 gap-x-5 gap-y-2 sm:grid-cols-4">
              {[0, 1, 2, 3].map((q) => (
                <label key={q} className="block">
                  <span className="field-label tabular-nums">
                    {formatDateDE(daten.termine[art][q])}
                  </span>
                  <input
                    className="input tabular-nums"
                    inputMode="decimal"
                    placeholder="0,00"
                    value={eingabe[art][q]}
                    onChange={(e) => setzen(art, q, e.target.value)}
                    aria-label={`${name} ${q + 1}. Rate ${jahr}`}
                  />
                </label>
              ))}
            </div>
            {geaendert(art) && (
              <button type="button" className="btn-primary btn-sm mt-2" disabled={busy} onClick={() => speichern(art)}>
                Speichern
              </button>
            )}
          </div>
        ))}
    </>
  );
}

// Abo-Link für Kalender-Apps; den Link gibt es nur direkt nach dem Erzeugen.
function KalenderAbo({ aktiv, onChanged }) {
  const [url, setUrl] = useState(null);
  const [kopiert, setKopiert] = useState(false);
  const [busy, setBusy] = useState(false);

  async function neu() {
    setBusy(true);
    try {
      const res = await api.post('/api/fristen/kalender');
      setKopiert(false);
      setUrl(`${window.location.origin}${res.data.pfad}`);
      await onChanged();
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  async function beenden() {
    if (!window.confirm('Kalender-Abo beenden? Der bisherige Link funktioniert dann nicht mehr.')) return;
    setBusy(true);
    try {
      await api.delete('/api/fristen/kalender');
      setUrl(null);
      await onChanged();
      toast.success('Kalender-Abo beendet.');
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setBusy(false);
    }
  }

  async function kopieren() {
    try {
      await navigator.clipboard.writeText(url);
      setKopiert(true);
    } catch {
      toast.error('Kopieren hat nicht geklappt — markiere den Link und kopiere ihn von Hand.');
    }
  }

  return (
    <>
      <SectionHead label="Erinnerungen im Kalender" />
      <p className="max-w-[46rem] text-[13px] leading-snug text-ink/60">
        Abonniere die offenen Fristen in deinem Kalender (iPhone, Android, Thunderbird, Outlook). Jede Frist ist ein
        ganztägiger Termin mit Erinnerung drei Tage vorher und am Morgen des Tages; Erledigtes verschwindet beim
        nächsten Abgleich. Manche Kalender, etwa Google, übernehmen die Erinnerungen aus Abos nicht — dort stellst du
        sie für den abonnierten Kalender selbst ein.
      </p>
      {url ? (
        <div className="mt-3 space-y-3">
          <label className="block">
            <span className="field-label">Abo-Link (wird nur jetzt angezeigt)</span>
            <input className="input" readOnly value={url} onFocus={(e) => e.currentTarget.select()} />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-primary" onClick={kopieren}>
              {kopiert ? 'Kopiert' : 'Link kopieren'}
            </button>
            <a className="btn-outline" href={url.replace(/^https?:/, 'webcal:')}>
              Im Kalender öffnen
            </a>
          </div>
          <p className="text-xs leading-snug text-ink/60">
            Wer den Link hat, sieht deine Fristen. Gib ihn nicht weiter; ein neuer Link macht den alten ungültig.
          </p>
        </div>
      ) : aktiv ? (
        <div className="mt-3 space-y-3">
          <p className="text-[13px] text-ink/80">
            Das Abo ist eingerichtet. Den Link zeigt Tab aus Sicherheitsgründen nur beim Erzeugen.
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-outline" disabled={busy} onClick={neu}>
              Neuen Link erzeugen
            </button>
            <button type="button" className="btn-outline" disabled={busy} onClick={beenden}>
              Abo beenden
            </button>
          </div>
        </div>
      ) : (
        <div className="mt-3">
          <button type="button" className="btn-primary" disabled={busy} onClick={neu}>
            Kalender-Abo einrichten
          </button>
        </div>
      )}
    </>
  );
}
