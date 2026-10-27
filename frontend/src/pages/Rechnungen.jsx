import { useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import AboModal from '../components/AboModal.jsx';
import KontakteModal from '../components/KontakteModal.jsx';
import BuchungModal from '../components/BuchungModal.jsx';
import { DialogFuss, PositionenEditor, SchalterZeile } from '../components/DialogParts.jsx';
import Dropdown from '../components/Dropdown.jsx';
import {
  IconBan, IconBookIn, IconButton, IconCheck, IconCircleCheck, IconFileText, IconPause, IconPencil, IconPlay,
  IconPlus, IconRepeat, IconSend, IconTrash, IconUsers, IconZap,
} from '../components/Icons.jsx';
import Modal from '../components/Modal.jsx';
import { Hinweis, KeinGewerbe, Leer, PageHeader, PUNKT, Row, SectionHead, Zustand } from '../components/PageParts.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro, formatDateDE, parseEuroToCent, centToInput, todayISO } from '../lib/format.js';
import { INTERVALL_LABELS, naechsterTermin } from '../lib/intervall.js';

// Status der Rechnung: Farbe des Kreises + Zustandswort (kein Chip).
const STATUS = {
  entwurf: { label: 'Entwurf', kind: 'out', ton: 'leise' },
  versendet: { label: 'Versendet', kind: 'warn', ton: 'warn' },
  bezahlt: { label: 'Bezahlt', kind: 'pos', ton: 'pos' },
  storniert: { label: 'Storniert', kind: 'neg', ton: 'neg' },
};
const INTERVALL = { monatlich: 'monatlich', vierteljaehrlich: 'vierteljährlich', jaehrlich: 'jährlich' };

// Warum keine USt auf der Rechnung steht — je Rechnung wählbar.
const STEUERHINWEIS_OPTIONS = [
  { value: 'ku19', label: 'Kleinunternehmer § 19 UStG (Standard)' },
  { value: 'vers4nr11', label: 'Steuerfrei § 4 Nr. 11 UStG (Versicherungsprovision)' },
];

function emptyRPos() {
  return { beschreibung: '', menge: '1', preisInput: '' };
}

async function openPdf(id) {
  try {
    const res = await api.get(`/api/rechnungen/${id}/pdf`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    window.open(url, '_blank', 'noopener');
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  } catch (e) {
    toast.error(apiError(e, 'PDF konnte nicht erstellt werden.'));
  }
}

export default function Rechnungen() {
  const { gewerbeId, jahr, gewerbe, reloadBadges } = useOutletContext();
  const { user } = useAuth();
  const [items, setItems] = useState([]);
  const [abos, setAbos] = useState([]);
  const [kategorien, setKategorien] = useState([]);
  const [mail, setMail] = useState(null); // { email, konfiguriert }
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);
  const [senden, setSenden] = useState(null); // rechnung
  const [einnahme, setEinnahme] = useState(null); // rechnung -> BuchungModal
  const [aboModal, setAboModal] = useState(null); // { abo? , prefill? }
  const [kontakte, setKontakte] = useState([]);
  const [kontakteModal, setKontakteModal] = useState(false);

  const gewerbeRow = gewerbe.find((g) => String(g.id) === String(gewerbeId));

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [r, kat, m, a, ko] = await Promise.all([
        api.get('/api/rechnungen', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/kategorien', { params: { jahr } }),
        api.get('/api/einstellungen/mail'),
        api.get('/api/rechnungsabos', { params: { gewerbe_id: gewerbeId } }),
        api.get('/api/kontakte', { params: { gewerbe_id: gewerbeId } }),
      ]);
      setItems(r.data);
      setKategorien(kat.data);
      setMail(m.data);
      setAbos(a.data);
      setKontakte(ko.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  async function setStatus(r, status) {
    try {
      await api.post(`/api/rechnungen/${r.id}/status`, { status });
      toast.success(status === 'bezahlt' ? 'Als bezahlt markiert.' : 'Status geändert.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function remove(r) {
    if (!window.confirm(`Entwurf ${r.nummer} wirklich löschen?`)) return;
    try {
      await api.delete(`/api/rechnungen/${r.id}`);
      toast.success('Gelöscht.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  // ── Abos (wiederkehrende Rechnungen) ──────────────────────────────────────
  async function runAbo(a) {
    try {
      const res = await api.post(`/api/rechnungsabos/${a.id}/run`);
      const d = res.data;
      toast.success(
        d.versendet
          ? `Rechnung ${d.nummer} erstellt und versendet.`
          : `Rechnung ${d.nummer} als Entwurf erstellt.${d.fehler ? ` (${d.fehler})` : ''}`,
        { duration: 7000 },
      );
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function toggleAbo(a) {
    try {
      await api.patch(`/api/rechnungsabos/${a.id}`, { aktiv: !a.aktiv });
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  async function removeAbo(a) {
    if (!window.confirm(`Abo für „${a.empfaenger_name}" löschen? Bestehende Rechnungen bleiben.`))
      return;
    try {
      await api.delete(`/api/rechnungsabos/${a.id}`);
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  const einnahmeKat = kategorien.find((k) => k.key === 'einnahme_ku');
  const courtageKat = kategorien.find((k) => k.key === 'einnahme_steuerfrei');
  // §4-Nr.11-Rechnungen (Courtage) landen als Einnahme in Zeile 16, sonst Zeile 12.
  const einnahmeKatFuer = (r) => (r.steuerhinweis === 'vers4nr11' && courtageKat) || einnahmeKat;

  if (!gewerbeId) return <KeinGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div>
      <PageHeader
        title="Rechnungen"
        accent={jahr}
        sub={`Fortlaufende Nummern, §19-Hinweis automatisch drauf · Versand von ${mail?.email || '…'}`}
      >
        <IconButton
          icon={IconUsers}
          label={`Kontakte${kontakte.length > 0 ? ` (${kontakte.length})` : ''}`}
          onClick={() => setKontakteModal(true)}
        />
        <button className="btn-primary" onClick={() => setEditing({ positionen: [emptyRPos()] })}>
          <IconPlus className="mr-1 h-4 w-4" /> Rechnung
        </button>
      </PageHeader>

      {(!gewerbeRow?.anschrift || (mail && !mail.konfiguriert)) && (
        <div className="mt-5 space-y-3">
          {!gewerbeRow?.anschrift && (
            <Hinweis ton="warn" titel="Absender fehlt">
              Hinterlege unter{' '}
              <Link to="/gewerbe" className="font-bold underline">
                Gewerbe
              </Link>{' '}
              deine Anschrift (und IBAN) — Pflichtangaben auf jeder Rechnung.
            </Hinweis>
          )}
          {mail && !mail.konfiguriert && (
            <Hinweis>
              Zum Versenden aus Tab einmalig den <strong>E-Mail-Versand einrichten</strong> (Profilzeile unten links)
              — App-Passwort deines Google-Kontos, Versand dann von {mail.email}. PDF-Download geht auch ohne.
            </Hinweis>
          )}
        </div>
      )}

      {abos.length > 0 && (
        <>
          <SectionHead label="Wiederkehrende Rechnungen" count={abos.length} />
          {abos.map((a) => (
            <Row
              key={a.id}
              icon={IconRepeat}
              muted={!a.aktiv}
              title={a.empfaenger_name}
              sub={
                <>
                  <span>{INTERVALL[a.intervall]}</span>
                  {PUNKT}
                  <span>nächste am {formatDateDE(a.naechste_am)}</span>
                  {PUNKT}
                  {!a.aktiv ? (
                    <Zustand>Pausiert</Zustand>
                  ) : a.auto_senden ? (
                    <Zustand ton="royal">Auto-Versand</Zustand>
                  ) : (
                    <span>Entwurf</span>
                  )}
                </>
              }
              amount={formatEuro(a.summe_cent)}
              actions={
                <>
                  <IconButton icon={IconZap} label="Jetzt ausführen" onClick={() => runAbo(a)} />
                  <IconButton icon={IconPencil} label="Bearbeiten" onClick={() => setAboModal({ abo: a })} />
                  <IconButton
                    icon={a.aktiv ? IconPause : IconPlay}
                    label={a.aktiv ? 'Pausieren' : 'Fortsetzen'}
                    onClick={() => toggleAbo(a)}
                  />
                  <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => removeAbo(a)} />
                </>
              }
            >
              {Boolean(a.auto_senden) && !a.absender_konfiguriert && (
                <Hinweis ton="warn" className="mt-1.5 !py-2 text-xs">
                  Absender {a.absender_email} hat kein App-Passwort hinterlegt — Rechnungen bleiben als Entwurf
                  liegen.
                </Hinweis>
              )}
            </Row>
          ))}
        </>
      )}

      <SectionHead label={`Rechnungen ${jahr}`} count={items.length} />
      {items.length === 0 ? (
        <Leer>
          Noch keine Rechnungen für {jahr}. Tipp: Nach der ersten Rechnung kannst du sie mit „Wiederholen…" als
          monatliches Abo anlegen.
        </Leer>
      ) : (
        items.map((r) => {
          const st = STATUS[r.status];
          return (
            <Row
              key={r.id}
              kind={st.kind}
              icon={IconFileText}
              muted={r.status === 'storniert'}
              title={
                <>
                  <span className="tabular-nums">{r.nummer}</span> · {r.empfaenger_name}
                </>
              }
              sub={
                <>
                  <Zustand ton={st.ton}>{st.label}</Zustand>
                  {PUNKT}
                  <span className="tabular-nums">{formatDateDE(r.datum)}</span>
                  {r.versendet_am && (
                    <>
                      {PUNKT}
                      <span>versendet {formatDateDE(r.versendet_am)}</span>
                    </>
                  )}
                  {r.bezahlt_am && (
                    <>
                      {PUNKT}
                      <span>bezahlt {formatDateDE(r.bezahlt_am)}</span>
                    </>
                  )}
                  {r.steuerhinweis === 'vers4nr11' && (
                    <>
                      {PUNKT}
                      <span>§4 Nr. 11</span>
                    </>
                  )}
                  {r.buchung_id && (
                    <>
                      {PUNKT}
                      <Zustand ton="royal" icon={IconCheck}>
                        Gebucht
                      </Zustand>
                    </>
                  )}
                </>
              }
              amount={formatEuro(r.summe_cent)}
              amountIn={r.status !== 'storniert'}
              /* feste Breite ab sm: Beträge bleiben bündig, PDF/Senden sitzen immer am selben Platz */
              actionsClass="sm:w-[12.75rem]"
              actions={
                <>
                  <IconButton icon={IconFileText} label="PDF ansehen" onClick={() => openPdf(r.id)} />
                  {r.status !== 'storniert' && (
                    <IconButton
                      icon={IconSend}
                      label={
                        !mail?.konfiguriert
                          ? 'Erst E-Mail-Versand im Profilmenü einrichten'
                          : r.status === 'versendet' || r.versendet_am
                            ? 'Erneut senden'
                            : 'Per E-Mail senden'
                      }
                      onClick={() => setSenden(r)}
                      disabled={!mail?.konfiguriert}
                    />
                  )}
                  {r.status === 'entwurf' && (
                    <IconButton
                      icon={IconPencil}
                      label="Bearbeiten"
                      onClick={() =>
                        setEditing({
                          id: r.id,
                          datum: r.datum,
                          leistungsdatum: r.leistungsdatum || '',
                          empfaenger_name: r.empfaenger_name,
                          empfaenger_anschrift: r.empfaenger_anschrift || '',
                          empfaenger_email: r.empfaenger_email || '',
                          notiz: r.notiz || '',
                          steuerhinweis: r.steuerhinweis || 'ku19',
                          positionen: r.positionen.map((p) => ({
                            beschreibung: p.beschreibung,
                            menge: String(p.menge).replace('.', ','),
                            preisInput: centToInput(p.einzelpreis_cent),
                          })),
                        })
                      }
                    />
                  )}
                  {(r.status === 'entwurf' || r.status === 'versendet') && (
                    <IconButton icon={IconCircleCheck} label="Als bezahlt markieren" onClick={() => setStatus(r, 'bezahlt')} />
                  )}
                  {r.status === 'bezahlt' && !r.buchung_id && einnahmeKat && (
                    <IconButton icon={IconBookIn} variant="primary" label="Als Einnahme buchen" onClick={() => setEinnahme(r)} />
                  )}
                  {r.status !== 'storniert' && (
                    <IconButton
                      icon={IconRepeat}
                      label="Als wiederkehrendes Abo anlegen…"
                      onClick={() => setAboModal({ prefill: r })}
                    />
                  )}
                  {r.status !== 'entwurf' && r.status !== 'storniert' && (
                    <IconButton icon={IconBan} variant="danger" label="Stornieren" onClick={() => setStatus(r, 'storniert')} />
                  )}
                  {r.status === 'entwurf' && (
                    <IconButton icon={IconTrash} variant="danger" label="Löschen" onClick={() => remove(r)} />
                  )}
                </>
              }
            />
          );
        })
      )}

      {editing && (
        <RechnungModal
          editing={editing}
          setEditing={setEditing}
          gewerbeId={gewerbeId}
          jahr={jahr}
          kontakte={kontakte}
          mailKonfiguriert={Boolean(mail?.konfiguriert)}
          onSaved={load}
        />
      )}

      {kontakteModal && (
        <KontakteModal gewerbeId={gewerbeId} onClose={() => setKontakteModal(false)} onChanged={load} />
      )}

      {senden && (
        <SendenModal rechnung={senden} user={user} onClose={() => setSenden(null)} onSent={load} />
      )}

      {aboModal && (
        <AboModal
          abo={aboModal.abo}
          prefill={aboModal.prefill}
          gewerbeId={gewerbeId}
          kontakte={kontakte}
          mailKonfiguriert={Boolean(mail?.konfiguriert)}
          onClose={() => setAboModal(null)}
          onSaved={load}
        />
      )}

      {einnahme && (
        <BuchungModal
          gewerbeId={gewerbeId}
          jahr={jahr}
          kategorien={kategorien}
          presetKategorieId={einnahmeKatFuer(einnahme)?.id}
          presetBetragCent={einnahme.summe_cent}
          presetBeschreibung={`Rechnung ${einnahme.nummer} – ${einnahme.empfaenger_name}`}
          rechnungId={einnahme.id}
          onClose={() => setEinnahme(null)}
          onSaved={async () => {
            await load();
            reloadBadges?.();
          }}
        />
      )}
    </div>
  );
}

function RechnungModal({ editing, setEditing, gewerbeId, jahr, kontakte = [], mailKonfiguriert, onSaved }) {
  const [busy, setBusy] = useState(false);
  const isEdit = Boolean(editing.id);
  const [form, setForm] = useState(() => ({
    datum: editing.datum || todayISO(),
    leistungsdatum: editing.leistungsdatum || '',
    empfaenger_name: editing.empfaenger_name || '',
    empfaenger_anschrift: editing.empfaenger_anschrift || '',
    empfaenger_email: editing.empfaenger_email || '',
    notiz: editing.notiz || '',
    steuerhinweis: editing.steuerhinweis || 'ku19',
    positionen: editing.positionen?.length ? editing.positionen : [emptyRPos()],
    wiederholen: false,
    intervall: 'monatlich',
    auto_senden: false,
  }));

  const total = useMemo(
    () =>
      form.positionen.reduce((s, p) => {
        const preis = parseEuroToCent(p.preisInput);
        const menge = Number(String(p.menge).replace(',', '.'));
        return s + (preis > 0 && menge > 0 ? Math.round(menge * preis) : 0);
      }, 0),
    [form.positionen],
  );

  // Gemeinsamer Payload für Speichern + Vorschau; null = Validierungsfehler (getoastet).
  function baueBody() {
    if (!form.empfaenger_name.trim()) {
      toast.error('Empfänger ist Pflicht.');
      return null;
    }
    const payloadPos = [];
    for (const p of form.positionen) {
      const preis = parseEuroToCent(p.preisInput);
      const menge = Number(String(p.menge).replace(',', '.'));
      if (!p.beschreibung.trim()) {
        toast.error('Jede Position braucht eine Beschreibung.');
        return null;
      }
      if (!preis || preis <= 0) {
        toast.error(`Bitte gültigen Preis für „${p.beschreibung}" angeben.`);
        return null;
      }
      if (!Number.isFinite(menge) || menge <= 0) {
        toast.error('Bitte gültige Menge angeben.');
        return null;
      }
      payloadPos.push({ beschreibung: p.beschreibung.trim(), menge, einzelpreis_cent: preis });
    }
    return {
      datum: form.datum,
      leistungsdatum: form.leistungsdatum.trim() || null,
      empfaenger_name: form.empfaenger_name.trim(),
      empfaenger_anschrift: form.empfaenger_anschrift.trim() || null,
      empfaenger_email: form.empfaenger_email.trim() || null,
      notiz: form.notiz.trim() || null,
      steuerhinweis: form.steuerhinweis,
      positionen: payloadPos,
    };
  }

  async function vorschau() {
    const body = baueBody();
    if (!body) return;
    setBusy(true);
    try {
      const res = await api.post(
        '/api/rechnungen/vorschau',
        { gewerbe_id: Number(gewerbeId), ...body },
        { responseType: 'blob' },
      );
      const url = URL.createObjectURL(res.data);
      window.open(url, '_blank', 'noopener');
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (err) {
      toast.error(apiError(err, 'Vorschau konnte nicht erstellt werden.'));
    } finally {
      setBusy(false);
    }
  }

  async function save(e) {
    e.preventDefault();
    const body = baueBody();
    if (!body) return;
    if (!isEdit && form.wiederholen && form.auto_senden && !body.empfaenger_email)
      return toast.error('Auto-Versand braucht eine Empfänger-E-Mail.');
    setBusy(true);
    try {
      if (isEdit) {
        await api.patch(`/api/rechnungen/${editing.id}`, body);
        toast.success('Gespeichert.');
      } else {
        const res = await api.post('/api/rechnungen', { gewerbe_id: Number(gewerbeId), ...body });
        if (form.wiederholen) {
          // Diese Rechnung ist die erste — das Abo übernimmt ab der nächsten Periode.
          const start = naechsterTermin(body.datum, form.intervall);
          try {
            await api.post('/api/rechnungsabos', {
              gewerbe_id: Number(gewerbeId),
              empfaenger_name: body.empfaenger_name,
              empfaenger_anschrift: body.empfaenger_anschrift,
              empfaenger_email: body.empfaenger_email,
              notiz: body.notiz,
              steuerhinweis: body.steuerhinweis,
              intervall: form.intervall,
              naechste_am: start,
              auto_senden: form.auto_senden,
              positionen: body.positionen,
            });
            toast.success(
              `Rechnung ${res.data.nummer} angelegt — wiederholt sich ${INTERVALL_LABELS[form.intervall]}, nächste am ${formatDateDE(start)}.`,
              { duration: 7000 },
            );
          } catch (aboErr) {
            toast.error(
              `Rechnung ${res.data.nummer} angelegt, aber das Abo konnte nicht erstellt werden: ${apiError(aboErr)}`,
              { duration: 10000 },
            );
          }
        } else {
          toast.success(`Rechnung ${res.data.nummer} angelegt.`);
        }
      }
      setEditing(null);
      await onSaved();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  const jahrMismatch = form.datum && String(form.datum).slice(0, 4) !== String(jahr);

  return (
    <Modal title={isEdit ? 'Rechnung bearbeiten' : 'Neue Rechnung'} onClose={() => setEditing(null)} maxWidth="max-w-2xl">
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
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
          <label className="block">
            <span className="field-label">Empfänger (Name/Firma)</span>
            <input className="input" value={form.empfaenger_name} autoFocus
              onChange={(e) => setForm({ ...form, empfaenger_name: e.target.value })} />
          </label>
          <label className="block">
            <span className="field-label">E-Mail (für den Versand)</span>
            <input className="input" value={form.empfaenger_email}
              onChange={(e) => setForm({ ...form, empfaenger_email: e.target.value })} placeholder="kunde@firma.de" />
          </label>
        </div>
        <label className="block">
          <span className="field-label">Anschrift Empfänger</span>
          <textarea className="input min-h-[64px]" value={form.empfaenger_anschrift}
            onChange={(e) => setForm({ ...form, empfaenger_anschrift: e.target.value })}
            placeholder={'Musterstraße 1\n20095 Hamburg'} />
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-5 gap-y-2">
          <label className="block">
            <span className="field-label">Rechnungsdatum</span>
            <input type="date" className="input" value={form.datum}
              onChange={(e) => setForm({ ...form, datum: e.target.value })} disabled={isEdit} />
          </label>
          <label className="block">
            <span className="field-label">Leistungsdatum/-zeitraum (optional)</span>
            <input className="input" value={form.leistungsdatum}
              onChange={(e) => setForm({ ...form, leistungsdatum: e.target.value })}
              placeholder="leer = Rechnungsdatum" />
          </label>
        </div>
        {jahrMismatch && !isEdit && (
          <Hinweis ton="warn" className="!py-2 text-xs">
            Das Datum liegt nicht im gewählten Jahr {jahr} — die Rechnung bekommt eine Nummer des Jahres{' '}
            {String(form.datum).slice(0, 4)} und erscheint dort.
          </Hinweis>
        )}

        <PositionenEditor
          positionen={form.positionen}
          onChange={(positionen) => setForm((f) => ({ ...f, positionen }))}
          summeCent={total}
          platzhalter="Leistung, z. B. Beratung März 2026"
        />

        <div className="block">
          <span className="field-label">Steuer-Hinweis (warum keine USt)</span>
          <Dropdown
            value={form.steuerhinweis}
            onChange={(v) => setForm({ ...form, steuerhinweis: String(v) })}
            options={STEUERHINWEIS_OPTIONS}
          />
        </div>

        <label className="block">
          <span className="field-label">Notiz auf der Rechnung (optional)</span>
          <input className="input" value={form.notiz}
            onChange={(e) => setForm({ ...form, notiz: e.target.value })}
            placeholder="z. B. Zahlbar innerhalb von 14 Tagen." />
        </label>

        {!isEdit && (
          <div>
            <SchalterZeile
              titel="Rechnung wiederholt sich"
              hinweis="Diese Rechnung ist die erste — Tab erstellt die folgenden automatisch als Abo."
              checked={form.wiederholen}
              onChange={(an) => setForm({ ...form, wiederholen: an })}
            />
            {form.wiederholen && (
              <div className="space-y-1 pt-3">
                <div className="flex flex-wrap items-center gap-3">
                  <Dropdown
                    value={form.intervall}
                    onChange={(v) => setForm({ ...form, intervall: String(v) })}
                    options={Object.entries(INTERVALL_LABELS).map(([value, label]) => ({ value, label }))}
                    variant="ghost"
                  />
                  <span className="text-[13px] tabular-nums text-ink/60">
                    nächste Rechnung am {formatDateDE(naechsterTermin(form.datum, form.intervall))}
                  </span>
                </div>
                <SchalterZeile
                  titel="Folge-Rechnungen automatisch senden"
                  hinweis={`Sonst entstehen sie als Entwurf. Braucht die Empfänger-E-Mail oben${!mailKonfiguriert ? ' und dein Mail-Konto (Profilzeile → E-Mail-Versand)' : ''}. Tipp: {monat} in der Positions-Beschreibung wird zum Abrechnungsmonat.`}
                  checked={form.auto_senden}
                  onChange={(an) => setForm({ ...form, auto_senden: an })}
                />
              </div>
            )}
          </div>
        )}

        <Hinweis className="text-xs">
          Der gewählte Steuer-Hinweis und Absender/IBAN aus den Gewerbe-Stammdaten kommen automatisch aufs PDF —
          das zugleich eine <strong>E-Rechnung</strong> ist (ZUGFeRD-XML eingebettet). §4-Nr.-11-Rechnungen werden
          bei „Als Einnahme buchen" der Kategorie „Umsatzsteuerfreie Einnahme (Courtage)" zugeordnet (Zeile 16).
        </Hinweis>

        <DialogFuss
          links={
            <button
              type="button"
              className="btn-outline"
              onClick={vorschau}
              disabled={busy}
              title="PDF aus den aktuellen Eingaben ansehen — speichert nichts, verbraucht keine Nummer"
            >
              Vorschau (PDF)
            </button>
          }
        >
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

function SendenModal({ rechnung, user, onClose, onSent }) {
  const [busy, setBusy] = useState(false);
  const [an, setAn] = useState(rechnung.empfaenger_email || '');
  const [betreff, setBetreff] = useState(`Rechnung ${rechnung.nummer}`);
  const [text, setText] = useState(
    `Guten Tag,\n\nanbei erhalten Sie die Rechnung ${rechnung.nummer} über ${formatEuro(rechnung.summe_cent)}.\n\nMit freundlichen Grüßen\n${user?.name || ''}`,
  );

  async function send(e) {
    e.preventDefault();
    if (!an.trim()) return toast.error('Bitte Empfänger-Adresse angeben.');
    setBusy(true);
    try {
      await api.post(`/api/rechnungen/${rechnung.id}/senden`, { an: an.trim(), betreff, text });
      toast.success(`Rechnung ${rechnung.nummer} versendet.`);
      onClose();
      await onSent();
    } catch (err) {
      toast.error(apiError(err), { duration: 8000 });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Rechnung ${rechnung.nummer} senden`} onClose={onClose}>
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
          PDF (E-Rechnung, ZUGFeRD) hängt automatisch an · Absender: {user?.email} (landet in deinem
          „Gesendet"-Ordner)
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
