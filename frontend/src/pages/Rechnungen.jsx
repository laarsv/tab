import { useEffect, useMemo, useState } from 'react';
import { Link, useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import AboModal from '../components/AboModal.jsx';
import KontakteModal from '../components/KontakteModal.jsx';
import BuchungModal from '../components/BuchungModal.jsx';
import Dropdown from '../components/Dropdown.jsx';
import Modal from '../components/Modal.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import { formatEuro, formatDateDE, parseEuroToCent, centToInput, todayISO } from '../lib/format.js';
import { INTERVALL_LABELS, naechsterTermin } from '../lib/intervall.js';

function NoGewerbe() {
  return (
    <div className="card p-12 text-center text-ink/60">
      Kein Gewerbe gewählt. Lege unter „Gewerbe" zuerst ein Gewerbe an.
    </div>
  );
}

const STATUS_CHIP = {
  entwurf: 'bg-ink/10 text-ink/70',
  versendet: 'bg-yellow-100 text-yellow-900',
  bezahlt: 'bg-royal text-paper',
  storniert: 'bg-red-100 text-red-900 line-through',
};
const STATUS_LABEL = { entwurf: 'Entwurf', versendet: 'Versendet', bezahlt: 'Bezahlt', storniert: 'Storniert' };

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

  if (!gewerbeId) return <NoGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Rechnungen {jahr}</h1>
          <p className="text-xs text-ink/60 mt-0.5">
            Fortlaufende Nummern, §19-Hinweis automatisch drauf · Versand von {mail?.email}
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button className="btn-outline btn-sm hidden sm:inline-flex" onClick={() => setKontakteModal(true)}>
            Kontakte{kontakte.length > 0 ? ` (${kontakte.length})` : ''}
          </button>
          <button className="btn-primary" onClick={() => setEditing({ positionen: [emptyRPos()] })}>
            + Rechnung
          </button>
        </div>
      </div>

      {!gewerbeRow?.anschrift && (
        <div className="p-4 rounded bg-yellow-100 text-yellow-900 text-sm">
          <strong>Absender fehlt:</strong> Hinterlege unter{' '}
          <Link to="/gewerbe" className="font-bold underline">Gewerbe</Link> deine Anschrift
          (und IBAN) — Pflichtangaben auf jeder Rechnung.
        </div>
      )}
      {mail && !mail.konfiguriert && (
        <div className="p-4 rounded bg-royal-soft/15 text-sm text-ink/80">
          Zum Versenden aus Tab einmalig den <strong>E-Mail-Versand einrichten</strong> (Profil-Menü
          oben rechts) — App-Passwort deines Google-Kontos, Versand dann von {mail.email}.
          PDF-Download geht auch ohne.
        </div>
      )}

      {abos.length > 0 && (
        <div className="card p-4 space-y-3">
          <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">
            Wiederkehrende Rechnungen (Abos)
          </div>
          <ul className="divide-y divide-ink/5">
            {abos.map((a) => (
              <li key={a.id} className="py-2.5 space-y-1.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0 text-sm">
                    <span className="font-bold">{a.empfaenger_name}</span>{' '}
                    <span className="text-ink/60">
                      · {{ monatlich: 'monatlich', vierteljaehrlich: 'vierteljährlich', jaehrlich: 'jährlich' }[a.intervall]}
                      {' '}· nächste am {formatDateDE(a.naechste_am)}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="tabular-nums font-bold text-sm">{formatEuro(a.summe_cent)}</span>
                    {!a.aktiv ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-ink/10 text-ink/60 text-[11px] font-bold">Pausiert</span>
                    ) : a.auto_senden ? (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-royal text-paper text-[11px] font-bold">Auto-Versand</span>
                    ) : (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-royal-soft/40 text-ink text-[11px] font-bold">Entwurf</span>
                    )}
                  </div>
                </div>
                {a.auto_senden && !a.absender_konfiguriert && (
                  <div className="text-xs text-yellow-900 bg-yellow-100 rounded px-2 py-1">
                    Absender {a.absender_email} hat kein App-Passwort hinterlegt — Rechnungen
                    bleiben als Entwurf liegen.
                  </div>
                )}
                <div className="flex flex-wrap gap-2">
                  <button className="btn-outline btn-sm" onClick={() => runAbo(a)}>Jetzt ausführen</button>
                  <button className="btn-ghost btn-sm" onClick={() => setAboModal({ abo: a })}>Bearbeiten</button>
                  <button className="btn-ghost btn-sm" onClick={() => toggleAbo(a)}>
                    {a.aktiv ? 'Pausieren' : 'Fortsetzen'}
                  </button>
                  <button className="btn-ghost btn-sm text-red-700" onClick={() => removeAbo(a)}>Löschen</button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {items.length === 0 ? (
        <div className="card p-12 text-center text-ink/60">
          Noch keine Rechnungen für {jahr}. Tipp: Nach der ersten Rechnung kannst du sie mit
          „Wiederholen…" als monatliches Abo anlegen.
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((r) => (
            <div key={r.id} className="card p-4 space-y-2">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-black tabular-nums">{r.nummer}</span>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold ${STATUS_CHIP[r.status]}`}>
                      {STATUS_LABEL[r.status]}
                    </span>
                    {r.steuerhinweis === 'vers4nr11' && (
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-royal-soft/40 text-ink text-[10px] font-bold uppercase tracking-wider">
                        §4 Nr. 11
                      </span>
                    )}
                  </div>
                  <div className="text-sm text-ink/70 mt-0.5 truncate">
                    {r.empfaenger_name} · {formatDateDE(r.datum)}
                    {r.versendet_am && ` · versendet ${formatDateDE(r.versendet_am)}`}
                    {r.bezahlt_am && ` · bezahlt ${formatDateDE(r.bezahlt_am)}`}
                  </div>
                </div>
                <div className="tabular-nums font-black shrink-0">{formatEuro(r.summe_cent)}</div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button className="btn-outline btn-sm" onClick={() => openPdf(r.id)}>PDF</button>
                {r.status !== 'storniert' && (
                  <button
                    className="btn-outline btn-sm"
                    onClick={() => setSenden(r)}
                    disabled={!mail?.konfiguriert}
                    title={mail?.konfiguriert ? '' : 'Erst E-Mail-Versand im Profil-Menü einrichten'}
                  >
                    {r.status === 'versendet' || r.versendet_am ? 'Erneut senden' : 'Per E-Mail senden'}
                  </button>
                )}
                {r.status === 'entwurf' && (
                  <button className="btn-ghost btn-sm" onClick={() => setEditing({
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
                  })}>
                    Bearbeiten
                  </button>
                )}
                {(r.status === 'entwurf' || r.status === 'versendet') && (
                  <button className="btn-ghost btn-sm" onClick={() => setStatus(r, 'bezahlt')}>
                    Als bezahlt markieren
                  </button>
                )}
                {r.status === 'bezahlt' && einnahmeKat && (
                  <button className="btn-primary btn-sm" onClick={() => setEinnahme(r)}>
                    Als Einnahme buchen
                  </button>
                )}
                {r.status !== 'storniert' && (
                  <button
                    className="btn-ghost btn-sm"
                    onClick={() => setAboModal({ prefill: r })}
                    title="Diese Rechnung als wiederkehrendes Abo anlegen"
                  >
                    Wiederholen…
                  </button>
                )}
                {r.status !== 'entwurf' && r.status !== 'storniert' && (
                  <button className="btn-ghost btn-sm text-red-700" onClick={() => setStatus(r, 'storniert')}>
                    Stornieren
                  </button>
                )}
                {r.status === 'entwurf' && (
                  <button className="btn-ghost btn-sm text-red-700" onClick={() => remove(r)}>
                    Löschen
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
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

  function setPos(i, patch) {
    setForm((f) => ({
      ...f,
      positionen: f.positionen.map((p, idx) => (idx === i ? { ...p, ...patch } : p)),
    }));
  }

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
    <Modal title={isEdit ? `Rechnung bearbeiten` : 'Neue Rechnung'} onClose={() => setEditing(null)} maxWidth="max-w-2xl">
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
          <div className="rounded-lg bg-yellow-100 text-yellow-900 p-2.5 text-xs">
            Das Datum liegt nicht im gewählten Jahr {jahr} — die Rechnung bekommt eine Nummer des
            Jahres {String(form.datum).slice(0, 4)} und erscheint dort.
          </div>
        )}

        <div className="space-y-2">
          <span className="field-label mb-0">Positionen</span>
          {form.positionen.map((p, i) => (
            <div key={i} className="rounded-lg border border-ink/10 p-3 space-y-2">
              <div className="flex items-start gap-2">
                <input className="input flex-1" value={p.beschreibung} placeholder="Leistung, z. B. Beratung März 2026"
                  onChange={(e) => setPos(i, { beschreibung: e.target.value })} />
                {form.positionen.length > 1 && (
                  <button type="button" className="p-2 rounded-md hover:bg-ink/5 text-ink/50 shrink-0"
                    onClick={() => setForm((f) => ({ ...f, positionen: f.positionen.filter((_, idx) => idx !== i) }))}
                    aria-label="Position entfernen">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-5 w-5">
                      <path d="M6 6l12 12M18 6L6 18" />
                    </svg>
                  </button>
                )}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="block">
                  <span className="field-label">Menge</span>
                  <input className="input tabular-nums" inputMode="decimal" value={p.menge}
                    onChange={(e) => setPos(i, { menge: e.target.value })} />
                </label>
                <label className="block">
                  <span className="field-label">Einzelpreis (€)</span>
                  <input className="input tabular-nums" inputMode="decimal" value={p.preisInput} placeholder="0,00"
                    onChange={(e) => setPos(i, { preisInput: e.target.value })} />
                </label>
              </div>
            </div>
          ))}
          <div className="flex items-center justify-between">
            <button type="button" className="btn-ghost btn-sm"
              onClick={() => setForm((f) => ({ ...f, positionen: [...f.positionen, emptyRPos()] }))}>
              + Position
            </button>
            <span className="text-sm text-ink/60 tabular-nums">Summe {formatEuro(total)}</span>
          </div>
        </div>

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
          <div className="rounded-lg border border-ink/10 p-3 space-y-2">
            <label className="flex items-start gap-2 text-sm">
              <input
                type="checkbox"
                className="mt-0.5 rounded border-ink/30 text-royal focus:ring-royal"
                checked={form.wiederholen}
                onChange={(e) => setForm({ ...form, wiederholen: e.target.checked })}
              />
              <span>
                <span className="font-bold">Rechnung wiederholt sich</span>
                <span className="block text-xs text-ink/60">
                  Diese Rechnung ist die erste — Tab erstellt die folgenden automatisch als Abo.
                </span>
              </span>
            </label>
            {form.wiederholen && (
              <div className="pl-6 space-y-2">
                <div className="flex flex-wrap items-center gap-3">
                  <Dropdown
                    value={form.intervall}
                    onChange={(v) => setForm({ ...form, intervall: String(v) })}
                    options={Object.entries(INTERVALL_LABELS).map(([value, label]) => ({ value, label }))}
                    variant="ghost"
                  />
                  <span className="text-xs text-ink/60 tabular-nums">
                    nächste Rechnung am {formatDateDE(naechsterTermin(form.datum, form.intervall))}
                  </span>
                </div>
                <label className="flex items-start gap-2 text-sm">
                  <input
                    type="checkbox"
                    className="mt-0.5 rounded border-ink/30 text-royal focus:ring-royal"
                    checked={form.auto_senden}
                    onChange={(e) => setForm({ ...form, auto_senden: e.target.checked })}
                  />
                  <span>
                    <span className="font-bold">Folge-Rechnungen automatisch senden</span>
                    <span className="block text-xs text-ink/60">
                      Sonst entstehen sie als Entwurf. Braucht die Empfänger-E-Mail oben
                      {!mailKonfiguriert && ' und dein Mail-Konto (Profil-Menü → E-Mail-Versand)'}.
                      Tipp: {'{monat}'} in der Positions-Beschreibung wird zum Abrechnungsmonat.
                    </span>
                  </span>
                </label>
              </div>
            )}
          </div>
        )}

        <div className="rounded-lg bg-royal-soft/10 p-2.5 text-xs text-ink/70">
          Der gewählte Steuer-Hinweis und Absender/IBAN aus den Gewerbe-Stammdaten kommen
          automatisch aufs PDF — das zugleich eine <strong>E-Rechnung</strong> ist
          (ZUGFeRD-XML eingebettet). §4-Nr.-11-Rechnungen werden bei „Als Einnahme buchen"
          der Kategorie „Umsatzsteuerfreie Einnahme (Courtage)" zugeordnet (Zeile 16).
        </div>

        <div className="flex flex-col-reverse sm:flex-row sm:justify-between gap-2 pt-2">
          <button
            type="button"
            className="btn-outline"
            onClick={vorschau}
            disabled={busy}
            title="PDF aus den aktuellen Eingaben ansehen — speichert nichts, verbraucht keine Nummer"
          >
            Vorschau (PDF)
          </button>
          <div className="flex flex-col-reverse sm:flex-row gap-2">
            <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>Abbrechen</button>
            <button type="submit" className="btn-primary" disabled={busy}>Speichern</button>
          </div>
        </div>
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
        <div className="text-xs text-ink/60">
          PDF (E-Rechnung, ZUGFeRD) hängt automatisch an · Absender: {user?.email} (landet in
          deinem „Gesendet"-Ordner)
        </div>
        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
          <button type="button" className="btn-ghost" onClick={onClose}>Abbrechen</button>
          <button type="submit" className="btn-primary" disabled={busy}>
            {busy ? 'Sendet…' : 'Senden'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
