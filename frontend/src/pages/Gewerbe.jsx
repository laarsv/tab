import { useEffect, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { IconBriefcase, IconButton, IconPause, IconPencil, IconPlay, IconPlus, IconTrash } from '../components/Icons.jsx';
import Dropdown from '../components/Dropdown.jsx';
import { ART_LABEL, KU, REGEL, artImJahr } from '../lib/besteuerung.js';
import { DialogFuss, Gruppe, SchalterZeile } from '../components/DialogParts.jsx';
import LogoFeld from '../components/LogoFeld.jsx';
import Modal from '../components/Modal.jsx';
import { Leer, PageHeader, PUNKT, Row } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { centToInput, parseEuroToCent } from '../lib/format.js';

// "1,27" -> 127 Basispunkte; leer -> null (keine Verzugszinsen); ungültig -> undefined.
function parseBasiszins(text) {
  const s = String(text ?? '').trim();
  if (!s) return null;
  const n = Number(s.replace(',', '.'));
  if (!Number.isFinite(n) || n < -10 || n > 20) return undefined;
  return Math.round(n * 100);
}

// Ganze Zahl im Bereich, sonst undefined.
function ganzeZahl(text, min, max) {
  const s = String(text ?? '').trim();
  const n = Number(s);
  return s !== '' && Number.isInteger(n) && n >= min && n <= max ? n : undefined;
}

// Umsatzsteuer-Voranmeldung (v35): Zeitraum + Dauerfristverlängerung, sofort gespeichert.
function VoranmeldungFeld({ gewerbe, onChanged }) {
  async function speichern(patch) {
    try {
      const res = await api.patch(`/api/gewerbe/${gewerbe.id}`, patch);
      onChanged(res.data);
    } catch (e) {
      toast.error(apiError(e));
    }
  }
  return (
    <div className="space-y-1">
      <div className="block">
        <span className="field-label">Umsatzsteuer-Voranmeldung</span>
        <Dropdown
          value={gewerbe.ustva_zeitraum || 'quartal'}
          onChange={(v) => speichern({ ustva_zeitraum: String(v) })}
          options={[
            { value: 'quartal', label: 'Vierteljährlich' },
            { value: 'monat', label: 'Monatlich' },
            { value: 'jahr', label: 'Keine (befreit, nur Jahreserklärung)' },
          ]}
        />
      </div>
      {gewerbe.ustva_zeitraum !== 'jahr' && (
        <SchalterZeile
          titel="Dauerfristverlängerung"
          hinweis="Abgabe einen Monat später. Monatliche Abgeber zahlen dafür eine Sondervorauszahlung (in ELSTER selbst eintragen)."
          checked={!!gewerbe.ustva_dauerfrist}
          onChange={(v) => speichern({ ustva_dauerfrist: v })}
        />
      )}
      <p className="text-xs leading-snug text-ink/60">
        Faustregel: Umsatzsteuer im Vorjahr über 9.000 € → monatlich, bis 9.000 € → vierteljährlich, bis 2.000 € kann das
        Finanzamt befreien. Maßgeblich ist, was das Finanzamt festlegt.
      </p>
    </div>
  );
}

// Besteuerung je Jahr (Regelbesteuerung als Option, EUER_KATEGORIEN.md §8): Liste der Wechsel + neuer Wechsel.
// Ein Wechsel gilt ab dem 1.1. des Jahres; der Server lehnt abgeschlossene Jahre und unpassende Buchungen ab.
function BesteuerungFeld({ gewerbe, onChanged }) {
  const diesesJahr = new Date().getFullYear();
  const aktuell = artImJahr(gewerbe, diesesJahr);
  const [abJahr, setAbJahr] = useState(String(diesesJahr + 1));
  const [art, setArt] = useState(aktuell === KU ? REGEL : KU);
  const [busy, setBusy] = useState(false);
  const wechsel = gewerbe.besteuerung_wechsel || [];

  async function setzen() {
    const j = Number(abJahr);
    if (!Number.isInteger(j) || j < 2000 || j > 2100) return toast.error('Bitte ein Jahr angeben, z. B. ' + (diesesJahr + 1) + '.');
    if (artImJahr(gewerbe, j) === art) return toast.error(`${j} gilt schon ${ART_LABEL[art]}.`);
    setBusy(true);
    try {
      const res = await api.put(`/api/gewerbe/${gewerbe.id}/besteuerung`, { ab_jahr: j, art });
      toast.success(`Ab 1.1.${j}: ${ART_LABEL[art]}.`);
      onChanged(res.data);
    } catch (e) {
      toast.error(apiError(e), { duration: 8000 });
    } finally {
      setBusy(false);
    }
  }

  async function entfernen(w) {
    if (!window.confirm(`Wechsel „ab ${w.ab_jahr}: ${ART_LABEL[w.art]}“ entfernen?`)) return;
    try {
      const res = await api.delete(`/api/gewerbe/${gewerbe.id}/besteuerung/${w.ab_jahr}`);
      onChanged(res.data);
    } catch (e) {
      toast.error(apiError(e), { duration: 8000 });
    }
  }

  return (
    <Gruppe titel="Besteuerung" className="border-t border-ink/[0.08] pt-4">
      <p className="text-[13.5px] leading-snug text-ink/80">
        {diesesJahr}: <strong>{ART_LABEL[aktuell]}</strong>
        {aktuell === KU ? ' — alles brutto, keine Umsatzsteuer.' : ' — Buchungen und Rechnungen mit Umsatzsteuer.'}
      </p>
      {wechsel.length > 0 && (
        <ul className="divide-y divide-ink/[0.06]">
          {wechsel.map((w) => (
            <li key={w.ab_jahr} className="flex items-center gap-2 py-1.5 text-[13.5px]">
              <span className="flex-1 tabular-nums">
                ab 1.1.{w.ab_jahr}: {ART_LABEL[w.art]}
              </span>
              <IconButton icon={IconTrash} variant="danger" label="Wechsel entfernen" onClick={() => entfernen(w)} />
            </li>
          ))}
        </ul>
      )}
      <div className="grid grid-cols-[minmax(0,7rem)_minmax(0,1fr)_auto] items-end gap-2">
        <label className="block">
          <span className="field-label">Ab Jahr</span>
          <input className="input tabular-nums" inputMode="numeric" value={abJahr} onChange={(e) => setAbJahr(e.target.value)} />
        </label>
        <div className="block">
          <span className="field-label">Besteuerung</span>
          <Dropdown
            value={art}
            onChange={(v) => setArt(String(v))}
            options={[
              { value: REGEL, label: ART_LABEL[REGEL] },
              { value: KU, label: ART_LABEL[KU] },
            ]}
          />
        </div>
        <button type="button" className="btn-outline btn-sm mb-0.5" disabled={busy} onClick={setzen}>
          Übernehmen
        </button>
      </div>
      {wechsel.some((w) => w.art === REGEL) && <VoranmeldungFeld gewerbe={gewerbe} onChanged={onChanged} />}
      <p className="text-xs leading-snug text-ink/60">
        Ein Wechsel gilt immer ab dem 1. Januar. Bei Regelbesteuerung buchst du Steuersatz und Umsatzsteuer je Position,
        Rechnungen weisen die Umsatzsteuer aus, und die Anlage EÜR bekommt die Umsatzsteuer-Zeilen. Ob und ab wann du
        wechseln musst, klär mit deiner Steuerberatung.
      </p>
    </Gruppe>
  );
}

const bpZuText = (bp) => (bp === null || bp === undefined ? '' : (bp / 100).toFixed(2).replace('.', ','));
const gebuehrText = (cent) => (cent ? centToInput(cent) : '');

export default function Gewerbe() {
  const { reloadGewerbe, setGewerbeId } = useOutletContext();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null); // {id?, name, steuernummer}

  async function load() {
    setLoading(true);
    try {
      const res = await api.get('/api/gewerbe', { params: { include_inactive: true } });
      setItems(res.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function save(e) {
    e.preventDefault();
    const body = {
      name: editing.name?.trim(),
      steuernummer: editing.steuernummer?.trim() || null,
      ...(editing.id ? {} : { besteuerung: editing.besteuerung || 'kleinunternehmer' }),
      ust_id: editing.ust_id?.trim() || null,
      anschrift: editing.anschrift?.trim() || null,
      iban: editing.iban?.trim() || null,
      kontoinhaber: editing.kontoinhaber?.trim() || null,
      rechnung_fusszeile: editing.rechnung_fusszeile?.trim() || null,
    };
    if (!body.name) return toast.error('Name ist Pflicht.');
    if (editing.id) {
      // Zahlung & Mahnwesen (nur beim Bearbeiten; ein neues Gewerbe startet mit den Standardwerten)
      const ziel = ganzeZahl(editing.zahlungsziel_tage, 0, 120);
      const mahnFrist = ganzeZahl(editing.mahn_frist_tage, 1, 90);
      const basis = parseBasiszins(editing.basiszins);
      const gebuehren = [1, 2, 3].map((n) =>
        editing[`gebuehr_${n}`]?.trim() ? parseEuroToCent(editing[`gebuehr_${n}`]) : 0,
      );
      if (ziel === undefined) return toast.error('Zahlungsziel: ganze Tage von 0 bis 120.');
      if (mahnFrist === undefined) return toast.error('Zahlungsfrist der Mahnung: ganze Tage von 1 bis 90.');
      if (gebuehren.some((g) => g === null || g < 0)) return toast.error('Mahngebühr: bitte einen gültigen Betrag eintragen.');
      if (basis === undefined) return toast.error('Basiszinssatz: bitte eine Zahl zwischen -10 und 20 eintragen.');
      body.zahlungsziel_tage = ziel;
      body.mahn_frist_tage = mahnFrist;
      body.mahn_gebuehr_1_cent = gebuehren[0];
      body.mahn_gebuehr_2_cent = gebuehren[1];
      body.mahn_gebuehr_3_cent = gebuehren[2];
      body.basiszinssatz_bp = basis;
    }
    try {
      if (editing.id) {
        await api.patch(`/api/gewerbe/${editing.id}`, body);
        toast.success('Gespeichert.');
      } else {
        const res = await api.post('/api/gewerbe', body);
        toast.success('Gewerbe angelegt.');
        setGewerbeId(String(res.data.id));
      }
      setEditing(null);
      await load();
      await reloadGewerbe();
    } catch (err) {
      toast.error(apiError(err));
    }
  }

  async function toggleAktiv(g) {
    try {
      await api.patch(`/api/gewerbe/${g.id}`, { aktiv: !g.aktiv });
      await load();
      await reloadGewerbe();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (loading) return <PageSpinner />;

  // Basiszinssatz bei der Bundesbank abfragen; gespeichert wird erst mit „Speichern".
  async function basiszinsAbrufen() {
    try {
      const res = await api.get('/api/mahnwesen/basiszinssatz');
      const wert = bpZuText(res.data.basiszinssatz_bp);
      const stand = `${res.data.monat.slice(5, 7)}/${res.data.monat.slice(0, 4)}`;
      if (res.data.aktuell) {
        setEditing((e) => ({ ...e, basiszins: wert }));
        toast.success(`Basiszinssatz ${wert} % eingetragen (Bundesbank, Stand ${stand}). Gilt nach dem Speichern.`, {
          duration: 7000,
        });
      } else {
        toast(
          `Die Bundesbank meldet ${wert} % mit Stand ${stand}; der Satz für das neue Halbjahr steht noch nicht in der Zeitreihe. Das Feld bleibt unverändert — später erneut abrufen oder von Hand eintragen.`,
          { duration: 10000 },
        );
      }
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  function neu() {
    setEditing({
      name: '',
      steuernummer: '',
      besteuerung: 'kleinunternehmer',
      ust_id: '',
      anschrift: '',
      iban: '',
      kontoinhaber: '',
      rechnung_fusszeile: '',
    });
  }

  return (
    <div>
      <PageHeader title="Gewerbe" sub="Eine EÜR pro Gewerbe. Deaktivieren statt löschen.">
        <button className="btn-primary" onClick={neu}>
          <IconPlus className="mr-1 h-4 w-4" /> Gewerbe
        </button>
      </PageHeader>

      <div className="mt-6">
        {items.length === 0 ? (
          <Leer>Noch kein Gewerbe angelegt. Lege dein erstes Gewerbe an (z. B. „Makler" oder „App").</Leer>
        ) : (
          items.map((g) => (
            <Row
              key={g.id}
              icon={IconBriefcase}
              title={g.name}
              muted={!g.aktiv}
              sub={
                <>
                  {(() => {
                    const j = new Date().getFullYear();
                    const jetzt = artImJahr(g, j);
                    const naechster = (g.besteuerung_wechsel || []).find((w) => w.ab_jahr > j);
                    return (
                      <span>
                        {jetzt === KU ? 'Kleinunternehmer §19' : 'Regelbesteuerung'}
                        {naechster && ` · ab ${naechster.ab_jahr} ${ART_LABEL[naechster.art]}`}
                      </span>
                    );
                  })()}
                  {PUNKT}
                  <span>{g.steuernummer ? `St.-Nr. ${g.steuernummer}` : 'keine Steuernummer'}</span>
                  {!g.aktiv && (
                    <>
                      {PUNKT}
                      <span className="font-bold">inaktiv</span>
                    </>
                  )}
                </>
              }
              actions={
                <>
                  <IconButton
                    icon={IconPencil}
                    label="Bearbeiten"
                    onClick={() =>
                      setEditing({
                        id: g.id,
                        name: g.name,
                        steuernummer: g.steuernummer || '',
                        besteuerung: g.besteuerung || 'kleinunternehmer',
                        besteuerung_wechsel: g.besteuerung_wechsel || [],
                        ustva_zeitraum: g.ustva_zeitraum || 'quartal',
                        ustva_dauerfrist: Boolean(g.ustva_dauerfrist),
                        ust_id: g.ust_id || '',
                        anschrift: g.anschrift || '',
                        iban: g.iban || '',
                        kontoinhaber: g.kontoinhaber || '',
                        rechnung_fusszeile: g.rechnung_fusszeile || '',
                        hat_logo: Boolean(g.hat_logo),
                        zahlungsziel_tage: String(g.zahlungsziel_tage ?? 14),
                        mahn_frist_tage: String(g.mahn_frist_tage ?? 10),
                        gebuehr_1: gebuehrText(g.mahn_gebuehr_1_cent),
                        gebuehr_2: gebuehrText(g.mahn_gebuehr_2_cent),
                        gebuehr_3: gebuehrText(g.mahn_gebuehr_3_cent),
                        basiszins: bpZuText(g.basiszinssatz_bp),
                      })
                    }
                  />
                  <IconButton
                    icon={g.aktiv ? IconPause : IconPlay}
                    label={g.aktiv ? 'Deaktivieren' : 'Aktivieren'}
                    onClick={() => toggleAktiv(g)}
                  />
                </>
              }
            />
          ))
        )}
      </div>

      {editing && (
        <Modal
          title={editing.id ? 'Gewerbe bearbeiten' : 'Neues Gewerbe'}
          onClose={() => setEditing(null)}
          maxWidth="max-w-xl"
        >
          <form onSubmit={save} className="space-y-4">
            <label className="block">
              <span className="field-label">Name</span>
              <input
                className="input"
                value={editing.name}
                onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                autoFocus
              />
            </label>
            <label className="block">
              <span className="field-label">Steuernummer (optional)</span>
              <input
                className="input"
                value={editing.steuernummer}
                onChange={(e) => setEditing({ ...editing, steuernummer: e.target.value })}
              />
            </label>

            <label className="block">
              <span className="field-label">Rechnungs-Absender: Name & Anschrift</span>
              <textarea
                className="input min-h-[80px]"
                value={editing.anschrift}
                onChange={(e) => setEditing({ ...editing, anschrift: e.target.value })}
                placeholder={'Max Mustermann\nMusterstraße 1\n20095 Hamburg'}
              />
              <span className="block text-xs text-ink/60 mt-1">
                Erscheint auf Rechnungen (Pflichtangabe).
              </span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
              <label className="block">
                <span className="field-label">IBAN (für Rechnungen)</span>
                <input
                  className="input"
                  value={editing.iban}
                  onChange={(e) => setEditing({ ...editing, iban: e.target.value })}
                  placeholder="DE12 3456 …"
                />
              </label>
              <label className="block">
                <span className="field-label">Rechnungs-Fußzeile (optional)</span>
                <input
                  className="input"
                  value={editing.rechnung_fusszeile}
                  onChange={(e) => setEditing({ ...editing, rechnung_fusszeile: e.target.value })}
                  placeholder="z. B. Bankname, Kontoinhaber"
                />
              </label>
            </div>

            <label className="block">
              <span className="field-label">Kontoinhaber (optional)</span>
              <input
                className="input"
                value={editing.kontoinhaber}
                maxLength={70}
                onChange={(e) => setEditing({ ...editing, kontoinhaber: e.target.value })}
                placeholder="leer = erste Zeile der Anschrift"
              />
              <span className="mt-1 block text-xs text-ink/60">
                Mit IBAN druckt Tab einen GiroCode auf Rechnung und Mahnung. Banken prüfen beim Überweisen, ob der
                Empfängername zum Konto passt — trag hier den Namen ein, auf den dein Konto läuft.
              </span>
            </label>

            {editing.id && (
              <Gruppe titel="Logo" className="border-t border-ink/[0.08] pt-4">
                <LogoFeld
                  gewerbeId={editing.id}
                  hatLogo={editing.hat_logo}
                  onChanged={(g) => {
                    setEditing((e) => ({ ...e, hat_logo: Boolean(g.hat_logo) }));
                    load();
                    reloadGewerbe();
                  }}
                />
              </Gruppe>
            )}

            {editing.id ? (
              <BesteuerungFeld
                gewerbe={editing}
                onChanged={(g) => {
                  setEditing((e) => ({ ...e, besteuerung: g.besteuerung, besteuerung_wechsel: g.besteuerung_wechsel || [], ustva_zeitraum: g.ustva_zeitraum, ustva_dauerfrist: g.ustva_dauerfrist }));
                  load();
                  reloadGewerbe();
                }}
              />
            ) : (
              <SchalterZeile
                titel="Kleinunternehmer §19 UStG"
                hinweis="An = alles brutto, keine Umsatzsteuer. Aus = Regelbesteuerung ab diesem Jahr (später unter „Besteuerung“ änderbar)."
                checked={(editing.besteuerung || 'kleinunternehmer') === 'kleinunternehmer'}
                onChange={(an) =>
                  setEditing({ ...editing, besteuerung: an ? 'kleinunternehmer' : 'regelbesteuerung' })
                }
              />
            )}
            <label className="block sm:max-w-xs">
              <span className="field-label">USt-IdNr. (optional)</span>
              <input
                className="input"
                value={editing.ust_id}
                maxLength={20}
                onChange={(e) => setEditing({ ...editing, ust_id: e.target.value })}
                placeholder="DE123456789"
              />
              <span className="mt-1 block text-xs text-ink/60">Steht auf Rechnungen und in der E-Rechnung, wenn ausgefüllt.</span>
            </label>

            {editing.id && (
              <Gruppe titel="Zahlung & Mahnwesen" className="border-t border-ink/[0.08] pt-4">
                <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
                  <label className="block">
                    <span className="field-label">Zahlungsziel neuer Rechnungen (Tage)</span>
                    <input
                      className="input"
                      inputMode="numeric"
                      value={editing.zahlungsziel_tage}
                      onChange={(e) => setEditing({ ...editing, zahlungsziel_tage: e.target.value })}
                    />
                  </label>
                  <label className="block">
                    <span className="field-label">Zahlungsfrist in Mahnungen (Tage)</span>
                    <input
                      className="input"
                      inputMode="numeric"
                      value={editing.mahn_frist_tage}
                      onChange={(e) => setEditing({ ...editing, mahn_frist_tage: e.target.value })}
                    />
                  </label>
                </div>
                <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-3">
                  {[
                    [1, 'Erinnerung'],
                    [2, '1. Mahnung'],
                    [3, 'Letzte Mahnung'],
                  ].map(([n, label]) => (
                    <label key={n} className="block">
                      <span className="field-label">Gebühr {label} (€)</span>
                      <input
                        className="input"
                        inputMode="decimal"
                        placeholder="0,00"
                        value={editing[`gebuehr_${n}`]}
                        onChange={(e) => setEditing({ ...editing, [`gebuehr_${n}`]: e.target.value })}
                      />
                    </label>
                  ))}
                </div>
                <div className="flex flex-wrap items-end gap-x-5 gap-y-2">
                  <label className="block w-full sm:w-56">
                    <span className="field-label">Basiszinssatz (% p. a.)</span>
                    <input
                      className="input"
                      inputMode="decimal"
                      placeholder="leer = keine Verzugszinsen"
                      value={editing.basiszins}
                      onChange={(e) => setEditing({ ...editing, basiszins: e.target.value })}
                    />
                  </label>
                  <button type="button" className="btn-outline" onClick={basiszinsAbrufen}>
                    Bei der Bundesbank abrufen
                  </button>
                </div>
                <p className="text-xs leading-snug text-ink/60">
                  Der Basiszinssatz ändert sich zum 1. Januar und 1. Juli. Verzugszinsen = Basiszins + 9 Punkte
                  (Geschäftskunden) bzw. + 5 Punkte (Verbraucher), § 288 BGB. Mahngebühren nur in der Höhe, in der dir
                  tatsächlich Kosten entstehen.
                </p>
              </Gruppe>
            )}

            <DialogFuss>
              <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>
                Abbrechen
              </button>
              <button type="submit" className="btn-primary">
                Speichern
              </button>
            </DialogFuss>
          </form>
        </Modal>
      )}
    </div>
  );
}
