import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import { DialogFuss, PositionenEditor, SchalterZeile } from '../components/DialogParts.jsx';
import VorlagenModal from '../components/VorlagenModal.jsx';
import { TextbausteinWahl } from '../components/Vorlagen.jsx';
import Dropdown from '../components/Dropdown.jsx';
import {
  IconArrowRight, IconBan, IconCheck, IconCircleCheck, IconCopy, IconFileText, IconPencil, IconPlus, IconSend,
  IconTrash, IconButton, IconBookmark,
} from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import { Hinweis, KeinGewerbe, Leer, PageHeader, PUNKT, Row, SectionHead, Zustand } from '../components/PageParts.jsx';
import RechnungenTabs from '../components/RechnungenTabs.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { addDays } from '../lib/fristen.js';
import { centToInput, formatDateDE, formatEuro, parseEuroToCent, todayISO } from '../lib/format.js';

const GUELTIG_TAGE = 30;
const STANDARD_EINLEITUNG = 'vielen Dank für Ihre Anfrage. Gerne biete ich Ihnen die folgenden Leistungen an:';
const STEUERHINWEIS_OPTIONS = [
  { value: 'ku19', label: 'Kleinunternehmer § 19 UStG (Standard)' },
  { value: 'vers4nr11', label: 'Steuerfrei § 4 Nr. 11 UStG (Versicherungsprovision)' },
];

// Zustand des Angebots: Farbe des Kreises + Wort. „Abgelaufen" ist abgeleitet (versendet, Frist vorbei).
function zustand(a) {
  if (a.status === 'entwurf') return { label: 'Entwurf', kind: 'out', ton: 'leise' };
  if (a.status === 'angenommen') return { label: 'Angenommen', kind: 'pos', ton: 'pos' };
  if (a.status === 'abgelehnt') return { label: 'Abgelehnt', kind: 'neg', ton: 'neg' };
  if (a.abgelaufen) return { label: 'Abgelaufen', kind: 'late', ton: 'late' };
  return { label: 'Offen', kind: 'warn', ton: 'warn' };
}

function leerePosition() {
  return { beschreibung: '', menge: '1', preisInput: '', optional: false };
}

async function openPdf(id) {
  try {
    const res = await api.get(`/api/angebote/${id}/pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    toast.error(apiError(e, 'PDF konnte nicht erstellt werden.'));
  }
}

const mengeZahl = (s) => Number(String(s).replace(',', '.'));
const positionBetrag = (p) => {
  const preis = parseEuroToCent(p.preisInput);
  const menge = mengeZahl(p.menge);
  return preis > 0 && menge > 0 ? Math.round(menge * preis) : 0;
};

// Angebote (Aufbau wie Haben): schreiben, per Mail senden, Antwort festhalten, mit einem Klick
// in einen Rechnungsentwurf umwandeln. Optionale Positionen zählen nicht zur Angebotssumme.
export default function Angebote() {
  const { gewerbeId, jahr, gewerbe, reloadBadges } = useOutletContext();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [kontakte, setKontakte] = useState([]);
  const [mail, setMail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [vorlagenModal, setVorlagenModal] = useState(false);
  const [senden, setSenden] = useState(null);
  const [umwandeln, setUmwandeln] = useState(null);

  const gewerbeRow = gewerbe.find((g) => String(g.id) === String(gewerbeId));

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [a, m, k] = await Promise.all([
        api.get('/api/angebote', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/einstellungen/mail'),
        api.get('/api/kontakte', { params: { gewerbe_id: gewerbeId } }),
      ]);
      setItems(a.data);
      setMail(m.data);
      setKontakte(k.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  async function setStatus(a, status, meldung) {
    try {
      await api.post(`/api/angebote/${a.id}/status`, { status });
      toast.success(meldung);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function kopieren(a) {
    try {
      const res = await api.post(`/api/angebote/${a.id}/kopie`);
      toast.success(`Kopie als Entwurf ${res.data.nummer} angelegt.`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function remove(a) {
    if (!window.confirm(`Entwurf ${a.nummer} wirklich löschen?`)) return;
    try {
      await api.delete(`/api/angebote/${a.id}`);
      toast.success('Gelöscht.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (!gewerbeId) return <KeinGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div>
      <PageHeader
        title="Angebote"
        accent={jahr}
        sub="Eigener Nummernkreis, optionale Positionen, nach der Zusage mit einem Klick eine Rechnung"
      >
        <IconButton icon={IconBookmark} label="Artikel & Texte" onClick={() => setVorlagenModal(true)} />
        <button className="btn-primary" onClick={() => setEditing({ positionen: [leerePosition()] })}>
          <IconPlus className="mr-1 h-4 w-4" /> Angebot
        </button>
      </PageHeader>
      <RechnungenTabs />

      {(!gewerbeRow?.anschrift || (mail && !mail.konfiguriert)) && (
        <div className="mt-5 space-y-3">
          {!gewerbeRow?.anschrift && (
            <Hinweis ton="warn" titel="Absender fehlt">
              Hinterlege unter{' '}
              <Link to="/gewerbe" className="font-bold underline">
                Gewerbe
              </Link>{' '}
              deine Anschrift — sie steht als Absender auf jedem Angebot.
            </Hinweis>
          )}
          {mail && !mail.konfiguriert && (
            <Hinweis>
              Zum Versenden aus Tab einmalig den <strong>E-Mail-Versand einrichten</strong> (Profil unten links → Einstellungen).
              PDF-Download geht auch ohne.
            </Hinweis>
          )}
        </div>
      )}

      <SectionHead label={`Angebote ${jahr}`} count={items.length} />
      {items.length === 0 ? (
        <Leer>
          Noch keine Angebote für {jahr}. Sagt der Kunde zu, wandelst du das Angebot mit einem Klick in eine
          Rechnung um — die Positionen werden übernommen, optionale auf Wunsch.
        </Leer>
      ) : (
        items.map((a) => {
          const st = zustand(a);
          return (
            <Row
              key={a.id}
              kind={st.kind}
              icon={IconFileText}
              muted={a.status === 'abgelehnt'}
              title={
                <>
                  <span className="tabular-nums">{a.nummer}</span> · {a.empfaenger_name}
                </>
              }
              sub={
                <>
                  <Zustand ton={st.ton}>
                    {st.label}
                    {a.antwort_am && (a.status === 'angenommen' || a.status === 'abgelehnt') && ` ${formatDateDE(a.antwort_am)}`}
                  </Zustand>
                  <>
                    {PUNKT}
                    <span className="tabular-nums">{formatDateDE(a.datum)}</span>
                  </>
                  {(a.status === 'entwurf' || a.status === 'versendet') && (
                    <>
                      {PUNKT}
                      <span>gültig bis {formatDateDE(a.gueltig_bis)}</span>
                    </>
                  )}
                  {a.versendet_am && a.status !== 'entwurf' && (
                    <>
                      {PUNKT}
                      <span>versendet {formatDateDE(a.versendet_am)}</span>
                    </>
                  )}
                  {a.optional_cent > 0 && (
                    <>
                      {PUNKT}
                      <span className="tabular-nums">+ {formatEuro(a.optional_cent)} optional</span>
                    </>
                  )}
                  {a.rechnung && (
                    <>
                      {PUNKT}
                      <Link to="/rechnungen" className="inline-flex items-center gap-1 font-bold tabular-nums text-royal">
                        <IconCheck className="h-3.5 w-3.5" />
                        Rechnung {a.rechnung.nummer}
                      </Link>
                    </>
                  )}
                </>
              }
              amount={formatEuro(a.summe_cent)}
              actions={
                <>
                  <IconButton icon={IconFileText} label="PDF ansehen" onClick={() => openPdf(a.id)} />
                  {a.status !== 'abgelehnt' && (
                    <IconButton
                      icon={IconSend}
                      label={
                        !mail?.konfiguriert
                          ? 'Erst E-Mail-Versand im Profilmenü einrichten'
                          : a.status === 'entwurf'
                            ? 'Per E-Mail senden'
                            : 'Erneut senden'
                      }
                      onClick={() => setSenden(a)}
                      disabled={!mail?.konfiguriert}
                    />
                  )}
                  {a.status === 'entwurf' && (
                    <>
                      <IconButton
                        icon={IconPencil}
                        label="Bearbeiten"
                        onClick={() =>
                          setEditing({
                            id: a.id,
                            datum: a.datum,
                            gueltig_bis: a.gueltig_bis,
                            empfaenger_name: a.empfaenger_name,
                            empfaenger_anschrift: a.empfaenger_anschrift || '',
                            empfaenger_email: a.empfaenger_email || '',
                            einleitung: a.einleitung || '',
                            notiz: a.notiz || '',
                            steuerhinweis: a.steuerhinweis || 'ku19',
                            positionen: a.positionen.map((p) => ({
                              beschreibung: p.beschreibung,
                              menge: String(p.menge).replace('.', ','),
                              preisInput: centToInput(p.einzelpreis_cent),
                              optional: p.art === 'optional',
                            })),
                          })
                        }
                      />
                      <IconButton
                        icon={IconCheck}
                        label="Als versendet markieren (ohne E-Mail)"
                        onClick={() => setStatus(a, 'versendet', 'Als versendet markiert.')}
                      />
                    </>
                  )}
                  {(a.status === 'versendet' || a.status === 'angenommen') && !a.rechnung_id && (
                    <IconButton
                      icon={IconArrowRight}
                      variant="primary"
                      label="In Rechnung umwandeln…"
                      onClick={() => setUmwandeln(a)}
                    />
                  )}
                  {a.status !== 'entwurf' && a.status !== 'angenommen' && (
                    <IconButton
                      icon={IconCircleCheck}
                      label={a.status === 'abgelehnt' ? 'Doch angenommen' : 'Angenommen'}
                      onClick={() => setStatus(a, 'angenommen', 'Als angenommen markiert.')}
                    />
                  )}
                  {a.status !== 'entwurf' && a.status !== 'abgelehnt' && !a.rechnung_id && (
                    <IconButton
                      icon={IconBan}
                      variant="danger"
                      label="Abgelehnt"
                      onClick={() => setStatus(a, 'abgelehnt', 'Als abgelehnt markiert.')}
                    />
                  )}
                  {a.status !== 'entwurf' && (
                    <IconButton icon={IconCopy} label="Als neuen Entwurf kopieren" onClick={() => kopieren(a)} />
                  )}
                  {a.status === 'entwurf' && (
                    <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => remove(a)} />
                  )}
                </>
              }
            />
          );
        })
      )}

      {vorlagenModal && <VorlagenModal gewerbeId={gewerbeId} onClose={() => setVorlagenModal(false)} />}
      {editing && (
        <AngebotModal
          editing={editing}
          setEditing={setEditing}
          gewerbeId={gewerbeId}
          jahr={jahr}
          kontakte={kontakte}
          onSaved={load}
        />
      )}
      {senden && <SendenModal angebot={senden} user={user} onClose={() => setSenden(null)} onSent={load} />}
      {umwandeln && (
        <UmwandelnModal
          angebot={umwandeln}
          onClose={() => setUmwandeln(null)}
          onDone={(res) => {
            setUmwandeln(null);
            reloadBadges?.();
            toast.success(`Rechnung ${res.rechnung.nummer} als Entwurf erstellt — prüfen und senden.`, { duration: 7000 });
            navigate('/rechnungen');
          }}
        />
      )}
    </div>
  );
}

function AngebotModal({ editing, setEditing, gewerbeId, jahr, kontakte = [], onSaved }) {
  const [busy, setBusy] = useState(false);
  const isEdit = Boolean(editing.id);
  const [gueltigEigen, setGueltigEigen] = useState(false); // Gültigkeit von Hand geändert → nicht mehr mitrechnen
  const [form, setForm] = useState(() => {
    const datum = editing.datum || todayISO();
    return {
      datum,
      gueltig_bis: editing.gueltig_bis || addDays(datum, GUELTIG_TAGE),
      empfaenger_name: editing.empfaenger_name || '',
      empfaenger_anschrift: editing.empfaenger_anschrift || '',
      empfaenger_email: editing.empfaenger_email || '',
      einleitung: isEdit ? editing.einleitung || '' : STANDARD_EINLEITUNG,
      notiz: editing.notiz || '',
      steuerhinweis: editing.steuerhinweis || 'ku19',
      positionen: editing.positionen?.length ? editing.positionen : [leerePosition()],
    };
  });

  const { summe, optional } = useMemo(
    () =>
      form.positionen.reduce(
        (s, p) => (p.optional ? { ...s, optional: s.optional + positionBetrag(p) } : { ...s, summe: s.summe + positionBetrag(p) }),
        { summe: 0, optional: 0 },
      ),
    [form.positionen],
  );

  function setDatum(datum) {
    setForm((f) => ({ ...f, datum, gueltig_bis: gueltigEigen || !datum ? f.gueltig_bis : addDays(datum, GUELTIG_TAGE) }));
  }

  async function save(e) {
    e.preventDefault();
    if (!form.empfaenger_name.trim()) return toast.error('Empfänger ist Pflicht.');
    if (!form.datum || !form.gueltig_bis) return toast.error('Datum und „Gültig bis" angeben.');
    if (form.gueltig_bis < form.datum) return toast.error('„Gültig bis" liegt vor dem Angebotsdatum.');
    const positionen = [];
    for (const p of form.positionen) {
      const preis = parseEuroToCent(p.preisInput);
      const menge = mengeZahl(p.menge);
      if (!p.beschreibung.trim()) return toast.error('Jede Position braucht eine Beschreibung.');
      if (!preis || preis <= 0) return toast.error(`Bitte gültigen Preis für „${p.beschreibung}" angeben.`);
      if (!Number.isFinite(menge) || menge <= 0) return toast.error('Bitte gültige Menge angeben.');
      positionen.push({ beschreibung: p.beschreibung.trim(), menge, einzelpreis_cent: preis, art: p.optional ? 'optional' : 'normal' });
    }
    if (!positionen.some((p) => p.art === 'normal'))
      return toast.error('Mindestens eine Position muss zur Angebotssumme zählen (nicht nur optionale).');
    const body = {
      datum: form.datum,
      gueltig_bis: form.gueltig_bis,
      empfaenger_name: form.empfaenger_name.trim(),
      empfaenger_anschrift: form.empfaenger_anschrift.trim() || null,
      empfaenger_email: form.empfaenger_email.trim() || null,
      einleitung: form.einleitung.trim() || null,
      notiz: form.notiz.trim() || null,
      steuerhinweis: form.steuerhinweis,
      positionen,
    };
    setBusy(true);
    try {
      if (isEdit) {
        await api.patch(`/api/angebote/${editing.id}`, body);
        toast.success('Gespeichert.');
      } else {
        const res = await api.post('/api/angebote', { gewerbe_id: Number(gewerbeId), ...body });
        toast.success(`Angebot ${res.data.nummer} angelegt.`);
      }
      setEditing(null);
      await onSaved();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  const angebotsJahr = isEdit ? String(editing.datum).slice(0, 4) : null;
  const jahrMismatch = !isEdit && form.datum && String(form.datum).slice(0, 4) !== String(jahr);

  return (
    <Modal title={isEdit ? 'Angebot bearbeiten' : 'Neues Angebot'} onClose={() => setEditing(null)} maxWidth="max-w-2xl">
      <form onSubmit={save} className="space-y-4">
        {kontakte.length > 0 && (
          <div className="block">
            <span className="field-label">Aus Kontakten übernehmen</span>
            <Dropdown
              value=""
              placeholder="Kontakt wählen…"
              searchable
              options={kontakte.map((k) => ({ value: String(k.id), label: k.name }))}
              onChange={(v) => {
                const k = kontakte.find((x) => String(x.id) === String(v));
                if (k)
                  setForm((f) => ({
                    ...f,
                    empfaenger_name: k.name,
                    empfaenger_anschrift: k.anschrift || '',
                    empfaenger_email: k.email || '',
                  }));
              }}
            />
          </div>
        )}
        <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
          <label className="block">
            <span className="field-label">Empfänger (Name/Firma)</span>
            <input className="input" value={form.empfaenger_name} autoFocus
              onChange={(e) => setForm({ ...form, empfaenger_name: e.target.value })} />
          </label>
          <label className="block">
            <span className="field-label">E-Mail (für den Versand)</span>
            <input className="input" value={form.empfaenger_email} placeholder="kunde@firma.de"
              onChange={(e) => setForm({ ...form, empfaenger_email: e.target.value })} />
          </label>
        </div>
        <label className="block">
          <span className="field-label">Anschrift Empfänger</span>
          <textarea className="input min-h-[64px]" value={form.empfaenger_anschrift}
            placeholder={'Musterstraße 1\n20095 Hamburg'}
            onChange={(e) => setForm({ ...form, empfaenger_anschrift: e.target.value })} />
        </label>
        <div className="grid grid-cols-1 gap-x-5 gap-y-2 sm:grid-cols-2">
          <label className="block">
            <span className="field-label">Angebotsdatum</span>
            <input type="date" className="input" value={form.datum}
              min={angebotsJahr ? `${angebotsJahr}-01-01` : undefined} max={angebotsJahr ? `${angebotsJahr}-12-31` : undefined}
              onChange={(e) => setDatum(e.target.value)} />
          </label>
          <label className="block">
            <span className="field-label">Gültig bis</span>
            <input type="date" className="input" value={form.gueltig_bis} min={form.datum}
              onChange={(e) => {
                setGueltigEigen(true);
                setForm({ ...form, gueltig_bis: e.target.value });
              }} />
          </label>
        </div>
        {jahrMismatch && (
          <Hinweis ton="warn" className="!py-2 text-xs">
            Das Datum liegt nicht im gewählten Jahr {jahr} — das Angebot bekommt eine Nummer des Jahres{' '}
            {String(form.datum).slice(0, 4)} und erscheint dort.
          </Hinweis>
        )}

        <div className="block">
          <div className="flex items-center justify-between gap-3">
            <span className="field-label">Einleitung (nach „Sehr geehrte Damen und Herren,")</span>
            <TextbausteinWahl gewerbeId={gewerbeId} aktuell={form.einleitung} onText={(t) => setForm({ ...form, einleitung: t })} />
          </div>
          <textarea className="input min-h-[64px]" value={form.einleitung}
            onChange={(e) => setForm({ ...form, einleitung: e.target.value })} />
        </div>

        <PositionenEditor
          positionen={form.positionen}
          onChange={(positionen) => setForm((f) => ({ ...f, positionen }))}
          summeCent={summe}
          optionalCent={optional}
          mitOptional
          platzhalter="Leistung, z. B. Konzept und Umsetzung"
          gewerbeId={gewerbeId}
        />

        <div className="block">
          <span className="field-label">Steuer-Hinweis (warum keine USt)</span>
          <Dropdown
            value={form.steuerhinweis}
            onChange={(v) => setForm({ ...form, steuerhinweis: String(v) })}
            options={STEUERHINWEIS_OPTIONS}
          />
        </div>
        <div className="block">
          <div className="flex items-center justify-between gap-3">
            <span className="field-label">Hinweis am Ende (optional)</span>
            <TextbausteinWahl gewerbeId={gewerbeId} aktuell={form.notiz} onText={(t) => setForm({ ...form, notiz: t })} />
          </div>
          <textarea className="input min-h-[56px]" value={form.notiz} placeholder="z. B. Zahlung nach Leistung."
            onChange={(e) => setForm({ ...form, notiz: e.target.value })} />
        </div>

        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            Speichern
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}

function SendenModal({ angebot, user, onClose, onSent }) {
  const [busy, setBusy] = useState(false);
  const [an, setAn] = useState(angebot.empfaenger_email || '');
  const [betreff, setBetreff] = useState(`Angebot ${angebot.nummer}`);
  const [text, setText] = useState(
    `Guten Tag,\n\nanbei erhalten Sie mein Angebot ${angebot.nummer} über ${formatEuro(angebot.summe_cent)}, gültig bis ${formatDateDE(angebot.gueltig_bis)}.\n\nBei Fragen melde ich mich gern.\n\nMit freundlichen Grüßen\n${user?.name || ''}`,
  );

  async function send(e) {
    e.preventDefault();
    if (!an.trim()) return toast.error('Bitte Empfänger-Adresse angeben.');
    setBusy(true);
    try {
      await api.post(`/api/angebote/${angebot.id}/senden`, { an: an.trim(), betreff, text });
      toast.success(`Angebot ${angebot.nummer} versendet.`);
      onClose();
      await onSent();
    } catch (err) {
      toast.error(apiError(err), { duration: 8000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Angebot ${angebot.nummer} senden`} onClose={onClose}>
      <form onSubmit={send} className="space-y-4">
        <label className="block">
          <span className="field-label">An</span>
          <input className="input" value={an} onChange={(e) => setAn(e.target.value)} placeholder="kunde@firma.de" autoFocus />
        </label>
        <label className="block">
          <span className="field-label">Betreff</span>
          <input className="input" value={betreff} onChange={(e) => setBetreff(e.target.value)} />
        </label>
        <label className="block">
          <span className="field-label">Nachricht</span>
          <textarea className="input min-h-[140px]" value={text} onChange={(e) => setText(e.target.value)} />
        </label>
        <p className="text-[13px] leading-snug text-ink/60">
          Das Angebot als PDF hängt automatisch an{angebot.status === 'entwurf' && ' — danach gilt es als versendet und ist nicht mehr änderbar'} ·
          Absender: {user?.email} (landet in deinem „Gesendet"-Ordner)
        </p>
        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Sendet…' : 'Senden'}
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}

// Rechnungsentwurf aus dem Angebot: die normalen Positionen kommen immer mit, optionale nach Wahl.
function UmwandelnModal({ angebot: a, onClose, onDone }) {
  const [datum, setDatum] = useState(todayISO());
  const [gewaehlt, setGewaehlt] = useState(() => new Set());
  const [busy, setBusy] = useState(false);
  const optionale = a.positionen.filter((p) => p.art === 'optional');
  const betrag = (p) => Math.round(p.menge * p.einzelpreis_cent);
  const summe = a.summe_cent + optionale.filter((p) => gewaehlt.has(p.id)).reduce((s, p) => s + betrag(p), 0);

  function schalte(id, an) {
    setGewaehlt((alt) => {
      const neu = new Set(alt);
      if (an) neu.add(id);
      else neu.delete(id);
      return neu;
    });
  }

  async function erstellen(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const res = await api.post(`/api/angebote/${a.id}/rechnung`, { optional_ids: [...gewaehlt], datum });
      await onDone(res.data);
    } catch (err) {
      toast.error(apiError(err));
      setBusy(false);
    }
  }

  return (
    <Modal title="In Rechnung umwandeln" subtitle={`Angebot ${a.nummer} · ${a.empfaenger_name}`} onClose={onClose}>
      <form onSubmit={erstellen} className="space-y-4">
        <p className="text-[13px] leading-snug text-ink/70">
          Es entsteht ein <strong>Rechnungsentwurf</strong> mit den Positionen des Angebots, den du vor dem Senden noch
          prüfen kannst. Das Angebot gilt danach als angenommen und abgerechnet.
        </p>
        {optionale.length > 0 && (
          <div>
            <div className="eyebrow mb-1">Optionale Positionen mitnehmen?</div>
            {optionale.map((p) => (
              <SchalterZeile
                key={p.id}
                titel={p.beschreibung}
                hinweis={`${String(p.menge).replace('.', ',')} × ${formatEuro(p.einzelpreis_cent)} = ${formatEuro(betrag(p))}`}
                checked={gewaehlt.has(p.id)}
                onChange={(an) => schalte(p.id, an)}
              />
            ))}
          </div>
        )}
        <label className="block max-w-[14rem]">
          <span className="field-label">Rechnungsdatum</span>
          <input type="date" className="input" value={datum} onChange={(e) => setDatum(e.target.value)} />
        </label>
        <p className="text-sm tabular-nums text-ink/70">
          Rechnungssumme <strong>{formatEuro(summe)}</strong>
        </p>
        <DialogFuss>
          <button type="button" className="btn-ghost" onClick={onClose}>
            Abbrechen
          </button>
          <button type="submit" className="btn-primary" disabled={busy || !datum}>
            Rechnung erstellen
          </button>
        </DialogFuss>
      </form>
    </Modal>
  );
}
