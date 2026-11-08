import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { SchalterZeile } from '../components/DialogParts.jsx';
import Dropdown from '../components/Dropdown.jsx';
import { Hinweis, PageHeader, SectionHead } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { centToInput, formatDateDE, formatEuro, parseEuroToCent } from '../lib/format.js';
import { formatProzent, mahnbetraege, openMahnungPdf, STUFEN } from '../lib/mahnwesen.js';

// Mahnung vorbereiten (Aufbau wie Haben): links das Formular, rechts die Forderungsaufstellung mit
// „Entwurf als PDF“ und „… erstellen“. Erstellte Mahnungen lassen sich nicht mehr ändern.
export default function MahnungNeu() {
  const { id } = useParams();
  const [draft, setDraft] = useState(null);
  const [fehler, setFehler] = useState(null);

  useEffect(() => {
    setDraft(null);
    setFehler(null);
    api
      .get(`/api/mahnwesen/entwurf/${id}`)
      .then((res) => setDraft(res.data))
      .catch((e) => setFehler(apiError(e, 'Mahnung konnte nicht vorbereitet werden.')));
  }, [id]);

  if (fehler) {
    return (
      <div>
        <PageHeader title="Mahnung" />
        <Hinweis ton="warn" className="mt-6">
          {fehler}{' '}
          <Link to="/rechnungen/mahnwesen" className="font-bold underline">
            Zurück zum Mahnwesen
          </Link>
        </Hinweis>
      </div>
    );
  }
  if (!draft) return <PageSpinner />;
  return <MahnungForm key={draft.rechnung.id} draft={draft} />;
}

function MahnungForm({ draft }) {
  const navigate = useNavigate();
  const { rechnung } = draft;
  const [stufe, setStufe] = useState(draft.stufe);
  const [frist, setFrist] = useState(draft.frist_am);
  const [gebuehr, setGebuehr] = useState(
    draft.gebuehren_cent[draft.stufe] ? centToInput(draft.gebuehren_cent[draft.stufe]) : '',
  );
  const gebuehrBearbeitet = useRef(false);
  const [zinsen, setZinsen] = useState(''); // '' | geschaeftskunde | verbraucher
  const [pauschale, setPauschale] = useState(false);
  const [einleitung, setEinleitung] = useState(draft.texte[draft.stufe].einleitung);
  const [schluss, setSchluss] = useState(draft.texte[draft.stufe].schluss);
  const [busy, setBusy] = useState(false);

  const gebuehrCent = gebuehr.trim() ? parseEuroToCent(gebuehr) : 0;
  const satzBp =
    zinsen && draft.basiszinssatz_bp !== null ? draft.basiszinssatz_bp + draft.aufschlag_bp[zinsen] : null;
  const betraege = mahnbetraege({
    offen: rechnung.offen_cent,
    faellig: rechnung.faellig_am,
    datum: draft.datum,
    gebuehr: gebuehrCent ?? 0,
    pauschale,
    satzBp,
  });
  const gueltig = gebuehrCent !== null && gebuehrCent >= 0 && frist > draft.datum && einleitung.trim() !== '';

  function waehleStufe(neu) {
    setStufe(neu);
    setEinleitung(draft.texte[neu].einleitung);
    setSchluss(draft.texte[neu].schluss);
    // Vorgabe-Gebühr der Stufe nur, solange sie nicht von Hand geändert wurde.
    if (!gebuehrBearbeitet.current) {
      setGebuehr(draft.gebuehren_cent[neu] ? centToInput(draft.gebuehren_cent[neu]) : '');
    }
  }

  function waehleZinsen(wert) {
    setZinsen(wert);
    if (wert === 'verbraucher') setPauschale(false); // Pauschale nur gegenüber Geschäftskunden
  }

  const body = () => ({
    rechnung_id: Number(rechnung.id),
    stufe,
    frist_am: frist,
    gebuehr_cent: gebuehrCent ?? 0,
    pauschale,
    zinsen: zinsen || null,
    einleitung,
    schluss,
  });

  async function entwurf() {
    if (!gueltig) return;
    setBusy(true);
    try {
      const res = await api.post('/api/mahnwesen/vorschau', body(), { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      // Bei blob-Antworten steckt die Fehlermeldung im Blob.
      let text = null;
      try {
        text = JSON.parse(await err.response?.data?.text?.())?.detail;
      } catch {
        /* keine JSON-Antwort */
      }
      toast.error(text || apiError(err, 'Entwurf konnte nicht erstellt werden.'));
    } finally {
      setBusy(false);
    }
  }

  async function erstellen(e) {
    e.preventDefault();
    if (!gueltig) return;
    setBusy(true);
    try {
      const res = await api.post('/api/mahnwesen', body());
      toast.success(`${STUFEN[stufe]} zu Rechnung ${rechnung.nummer} erstellt.`);
      openMahnungPdf(res.data.id);
      navigate('/rechnungen/mahnwesen');
    } catch (err) {
      toast.error(apiError(err));
      setBusy(false);
    }
  }

  return (
    <div>
      <div className="eyebrow">
        <Link to="/rechnungen/mahnwesen" className="hover:underline">
          Mahnwesen
        </Link>{' '}
        › Rechnung {rechnung.nummer}
      </div>
      <PageHeader title={STUFEN[stufe]} />

      <form onSubmit={erstellen} className="mt-2 grid gap-x-12 gap-y-2 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section aria-label="Mahnung">
          <SectionHead label="Mahnung" className="!mt-4" />
          <p className="text-[13px] leading-snug text-ink/60">
            Rechnung {rechnung.nummer} an {rechnung.empfaenger_name} vom {formatDateDE(rechnung.datum)}, fällig seit{' '}
            {formatDateDE(rechnung.faellig_am)} ({rechnung.tage_ueberfaellig} Tage), offen{' '}
            {formatEuro(rechnung.offen_cent)}.
          </p>

          <div className="mt-3 grid grid-cols-1 gap-x-5 gap-y-3 sm:grid-cols-2">
            <div className="block">
              <span className="field-label">Stufe</span>
              <Dropdown
                value={stufe}
                onChange={(v) => waehleStufe(Number(v))}
                options={[1, 2, 3]
                  .filter((s) => s >= draft.stufe)
                  .map((s) => ({ value: s, label: STUFEN[s] }))}
              />
            </div>
            <label className="block">
              <span className="field-label">Neue Zahlungsfrist</span>
              <input
                type="date"
                className="input"
                value={frist}
                min={draft.datum}
                onChange={(e) => setFrist(e.target.value)}
                aria-invalid={frist <= draft.datum}
              />
            </label>
            <label className="block">
              <span className="field-label">Mahngebühr (€)</span>
              <input
                className="input"
                inputMode="decimal"
                value={gebuehr}
                placeholder="0,00"
                onChange={(e) => {
                  gebuehrBearbeitet.current = true;
                  setGebuehr(e.target.value);
                }}
                aria-invalid={gebuehrCent === null}
              />
            </label>
            <div className="block">
              <span className="field-label">Verzugszinsen</span>
              <Dropdown
                value={zinsen}
                disabled={draft.basiszinssatz_bp === null}
                onChange={(v) => waehleZinsen(String(v))}
                options={[
                  { value: '', label: 'keine' },
                  { value: 'geschaeftskunde', label: 'Geschäftskunde, +9 Punkte' },
                  { value: 'verbraucher', label: 'Verbraucher, +5 Punkte' },
                ]}
              />
              <span className="mt-1 block text-xs text-ink/60">
                {draft.basiszinssatz_bp === null ? (
                  <>
                    Für Zinsen den Basiszinssatz beim{' '}
                    <Link to="/gewerbe" className="font-bold underline">
                      Gewerbe
                    </Link>{' '}
                    eintragen.
                  </>
                ) : (
                  `Basiszinssatz ${formatProzent(draft.basiszinssatz_bp)} plus Aufschlag nach § 288 BGB`
                )}
              </span>
            </div>
          </div>

          <div className="mt-3">
            <SchalterZeile
              titel="Verzugspauschale 40 €"
              hinweis="Nur gegenüber Geschäftskunden (§ 288 Abs. 5 BGB). Eine Mahngebühr wird darauf angerechnet."
              checked={pauschale}
              disabled={zinsen === 'verbraucher'}
              onChange={setPauschale}
            />
          </div>

          <label className="mt-3 block">
            <span className="field-label">Einleitung</span>
            <textarea
              className="input min-h-[96px]"
              value={einleitung}
              maxLength={2000}
              onChange={(e) => setEinleitung(e.target.value)}
            />
          </label>
          <label className="mt-3 block">
            <span className="field-label">Schluss</span>
            <textarea
              className="input min-h-[72px]"
              value={schluss}
              maxLength={2000}
              onChange={(e) => setSchluss(e.target.value)}
            />
          </label>
        </section>

        <section aria-label="Forderung">
          <SectionHead label="Forderung" className="!mt-4" />
          <dl className="mt-1 text-[15px]">
            <Zeile label="Offener Rechnungsbetrag" wert={formatEuro(betraege.offen)} />
            {betraege.gebuehr > 0 && <Zeile label="Mahngebühr" wert={formatEuro(betraege.gebuehr)} />}
            {betraege.pauschale > 0 && <Zeile label="Verzugspauschale" wert={formatEuro(betraege.pauschale)} />}
            {betraege.zinsen > 0 && (
              <Zeile
                label={`Zinsen ${formatProzent(betraege.zinssatzBp)} für ${betraege.zinstage} Tage`}
                wert={formatEuro(betraege.zinsen)}
              />
            )}
            <div className="mt-1 flex items-baseline justify-between gap-3 border-t border-ink/[0.08] pt-2.5">
              <dt className="font-black">Zu zahlen</dt>
              <dd className="font-black tabular-nums text-royal">{formatEuro(betraege.gesamt)}</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs leading-snug text-ink/60">
            Die Mahnung wird als PDF gespeichert und lässt sich danach nicht mehr ändern. Gebühren und Zinsen sind
            keine Rechnung: Zahlt der Kunde sie, buchst du den Mehrbetrag als zusätzliche Einnahme (sonstige
            Betriebseinnahmen).
          </p>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:flex-wrap">
            <button type="button" className="btn-outline" disabled={busy || !gueltig} onClick={entwurf}>
              Entwurf als PDF
            </button>
            <button type="submit" className="btn-primary" disabled={busy || !gueltig}>
              {STUFEN[stufe]} erstellen
            </button>
          </div>
        </section>
      </form>
    </div>
  );
}

function Zeile({ label, wert }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1">
      <dt className="text-ink/70">{label}</dt>
      <dd className="tabular-nums">{wert}</dd>
    </div>
  );
}
