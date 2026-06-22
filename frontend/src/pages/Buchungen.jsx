import { useEffect, useMemo, useState } from 'react';
import { useOutletContext } from 'react-router-dom';
import toast from 'react-hot-toast';
import { api, apiError } from '../api/client.js';
import Dropdown from '../components/Dropdown.jsx';
import Modal from '../components/Modal.jsx';
import BelegeSection from '../components/BelegeSection.jsx';
import { PageSpinner } from '../components/Spinner.jsx';
import {
  formatEuro,
  formatDateDE,
  parseEuroToCent,
  centToInput,
  todayISO,
  KM_SATZ_CENT,
} from '../lib/format.js';

const BELEG_PLACEHOLDER = {
  bewirtung: 'Pflichtangaben: Ort, Tag, Teilnehmer, Anlass (ab 150 € mit Namen).',
  geschenke: 'Pflichtangaben: Empfänger (Name), Anlass.',
};

function NoGewerbe() {
  return (
    <div className="card p-12 text-center text-ink/60">
      Kein Gewerbe gewählt. Lege oben links bzw. unter „Gewerbe" zuerst ein Gewerbe an.
    </div>
  );
}

export default function Buchungen() {
  const { gewerbeId, jahr } = useOutletContext();
  const [kategorien, setKategorien] = useState([]);
  const [items, setItems] = useState([]);
  const [kennzahlen, setKennzahlen] = useState(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(null);

  const katById = useMemo(() => {
    const m = {};
    kategorien.forEach((k) => (m[k.id] = k));
    return m;
  }, [kategorien]);

  async function load() {
    if (!gewerbeId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [kat, buch, kenn] = await Promise.all([
        api.get('/api/kategorien', { params: { jahr } }),
        api.get('/api/buchungen', { params: { gewerbe_id: gewerbeId, jahr } }),
        api.get('/api/kennzahlen', { params: { gewerbe_id: gewerbeId, jahr } }),
      ]);
      setKategorien(kat.data);
      setItems(buch.data);
      setKennzahlen(kenn.data);
    } catch (e) {
      toast.error(apiError(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [gewerbeId, jahr]); // eslint-disable-line react-hooks/exhaustive-deps

  async function remove(id) {
    if (!window.confirm('Diese Buchung wirklich löschen?')) return;
    try {
      await api.delete(`/api/buchungen/${id}`);
      toast.success('Gelöscht.');
      await load();
    } catch (e) {
      toast.error(apiError(e));
    }
  }

  if (!gewerbeId) return <NoGewerbe />;
  if (loading) return <PageSpinner />;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl sm:text-3xl font-black tracking-tight">Buchungen {jahr}</h1>
          <p className="text-xs text-ink/60 mt-0.5">Datum = Zahlungsdatum · Beträge brutto.</p>
        </div>
        <button
          className="btn-primary w-full sm:w-auto"
          onClick={() =>
            setEditing({ datum: todayISO(), betragInput: '', kategorie_id: '', beschreibung: '', beleg_details: '', km: '' })
          }
        >
          + Buchung
        </button>
      </div>

      {kennzahlen && <KuGuard k={kennzahlen} />}

      {kennzahlen && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Kennzahl label="Einnahmen" cent={kennzahlen.einnahmen_cent} />
          <Kennzahl label="Ausgaben" cent={kennzahlen.ausgaben_cent} />
          <Kennzahl
            label="Saldo (ohne AfA)"
            cent={kennzahlen.einnahmen_cent - kennzahlen.ausgaben_cent}
          />
        </div>
      )}

      {items.length === 0 ? (
        <div className="card p-12 text-center text-ink/60">Keine Buchungen für {jahr}.</div>
      ) : (
        <>
          {/* Desktop */}
          <div className="hidden md:block overflow-x-auto card">
            <table className="w-full text-sm">
              <thead className="text-left text-ink/60 text-xs uppercase tracking-wider">
                <tr className="border-b border-ink/10">
                  <th className="px-4 py-3">Datum</th>
                  <th className="px-4 py-3">Kategorie</th>
                  <th className="px-4 py-3">Beschreibung</th>
                  <th className="px-4 py-3 text-right">Betrag</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((b) => (
                  <tr key={b.id} className="border-b border-ink/5 last:border-b-0">
                    <td className="px-4 py-3 text-ink/70 whitespace-nowrap">{formatDateDE(b.datum)}</td>
                    <td className="px-4 py-3">
                      <span className={b.kategorie_typ === 'einnahme' ? 'text-mint font-bold' : ''}>
                        {b.kategorie_name}
                      </span>
                      {b.beleg_count > 0 && <Paperclip count={b.beleg_count} />}
                    </td>
                    <td className="px-4 py-3 text-ink/70">{b.beschreibung}</td>
                    <td className="px-4 py-3 text-right tabular-nums whitespace-nowrap">
                      {b.kategorie_typ === 'einnahme' ? '+' : '−'}
                      {formatEuro(b.betrag_cent)}
                    </td>
                    <td className="px-4 py-3 text-right whitespace-nowrap">
                      <button className="btn-ghost btn-sm" onClick={() => setEditing(toEdit(b))}>
                        Bearbeiten
                      </button>
                      <button className="btn-ghost btn-sm text-red-700" onClick={() => remove(b.id)}>
                        Löschen
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile */}
          <div className="md:hidden space-y-3">
            {items.map((b) => (
              <div key={b.id} className="card p-4 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-ink/60">{formatDateDE(b.datum)}</span>
                  <span className="tabular-nums font-bold">
                    {b.kategorie_typ === 'einnahme' ? '+' : '−'}
                    {formatEuro(b.betrag_cent)}
                  </span>
                </div>
                <div className="font-bold text-sm flex items-center">
                  {b.kategorie_name}
                  {b.beleg_count > 0 && <Paperclip count={b.beleg_count} />}
                </div>
                {b.beschreibung && <div className="text-sm text-ink/70">{b.beschreibung}</div>}
                <div className="flex gap-2 pt-1">
                  <button className="btn-outline btn-sm" onClick={() => setEditing(toEdit(b))}>
                    Bearbeiten
                  </button>
                  <button className="btn-ghost btn-sm text-red-700" onClick={() => remove(b.id)}>
                    Löschen
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {editing && (
        <BuchungModal
          editing={editing}
          setEditing={setEditing}
          kategorien={kategorien}
          katById={katById}
          gewerbeId={gewerbeId}
          onSaved={load}
        />
      )}
    </div>
  );
}

function toEdit(b) {
  return {
    id: b.id,
    datum: b.datum,
    betragInput: centToInput(b.betrag_cent),
    kategorie_id: String(b.kategorie_id),
    beschreibung: b.beschreibung || '',
    beleg_details: b.beleg_details || '',
    km: '',
  };
}

function Paperclip({ count }) {
  return (
    <span
      className="ml-2 inline-flex items-center gap-1 align-middle text-ink/50 text-xs"
      title={`${count} Beleg(e)`}
    >
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-3.5 w-3.5">
        <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" />
      </svg>
      <span className="tabular-nums">{count}</span>
    </span>
  );
}

function Kennzahl({ label, cent }) {
  return (
    <div className="card p-4">
      <div className="text-[11px] font-bold tracking-wider text-ink/60 uppercase">{label}</div>
      <div className="text-xl font-black tabular-nums mt-1">{formatEuro(cent)}</div>
    </div>
  );
}

function KuGuard({ k }) {
  if (k.ku_warn_laufend) {
    return (
      <div className="p-4 rounded flex items-start gap-3 bg-red-50 border-l-4 border-red-500 text-red-900">
        <div>
          <div className="font-bold">Kleinunternehmer-Grenze gerissen</div>
          <div className="text-sm mt-0.5">
            Einnahmen {formatEuro(k.einnahmen_cent)} überschreiten die laufende Grenze von{' '}
            {formatEuro(k.ku_grenze_laufend_cent)}. Der KU-Status entfällt — bitte Steuerberater
            kontaktieren. Tab deckt die Regelbesteuerung nicht ab.
          </div>
        </div>
      </div>
    );
  }
  if (k.ku_warn_vorjahr) {
    return (
      <div className="p-4 rounded flex items-start gap-3 bg-yellow-100 text-yellow-900">
        <div>
          <div className="font-bold">Vorjahresgrenze überschritten</div>
          <div className="text-sm mt-0.5">
            Einnahmen {formatEuro(k.einnahmen_cent)} liegen über {formatEuro(k.ku_grenze_vorjahr_cent)}.
            Für das Folgejahr ggf. kein KU mehr — im Blick behalten, im Zweifel Steuerberater fragen.
          </div>
        </div>
      </div>
    );
  }
  return null;
}

function BuchungModal({ editing, setEditing, kategorien, katById, gewerbeId, onSaved }) {
  const [busy, setBusy] = useState(false);
  const selKat = editing.kategorie_id ? katById[editing.kategorie_id] : null;
  const isKm = selKat?.key === 'fahrtkosten_kfz';
  const isGwg = selKat?.key === 'gwg';
  const isBewirtung = selKat?.key === 'bewirtung';
  const needsBeleg = Boolean(selKat?.belegpflicht_extra);

  const options = kategorien
    .filter((k) => !k.ist_afa)
    .map((k) => ({
      value: String(k.id),
      label: k.euer_zeile ? `${k.name} · Zeile ${k.euer_zeile}` : k.name,
    }));

  const computedKmBetrag =
    isKm && editing.km !== '' && Number.isFinite(Number(String(editing.km).replace(',', '.')))
      ? Math.round(Number(String(editing.km).replace(',', '.')) * KM_SATZ_CENT)
      : null;

  async function save(e) {
    e.preventDefault();
    if (!editing.kategorie_id) return toast.error('Bitte Kategorie wählen.');

    let betrag_cent;
    if (isKm && computedKmBetrag !== null) {
      betrag_cent = computedKmBetrag;
    } else {
      betrag_cent = parseEuroToCent(editing.betragInput);
    }
    if (!betrag_cent || betrag_cent <= 0) return toast.error('Bitte gültigen Betrag eingeben.');
    if (needsBeleg && !editing.beleg_details.trim())
      return toast.error('Beleg-Details sind für diese Kategorie Pflicht.');

    let beschreibung = editing.beschreibung.trim();
    if (isKm && computedKmBetrag !== null && !beschreibung) {
      beschreibung = `${editing.km} km × 0,30 €/km`;
    }

    const body = {
      gewerbe_id: Number(gewerbeId),
      datum: editing.datum,
      betrag_cent,
      kategorie_id: Number(editing.kategorie_id),
      beschreibung: beschreibung || null,
      beleg_details: needsBeleg ? editing.beleg_details.trim() : null,
    };

    setBusy(true);
    try {
      if (editing.id) {
        await api.patch(`/api/buchungen/${editing.id}`, body);
        toast.success('Gespeichert.');
      } else {
        await api.post('/api/buchungen', body);
        toast.success('Buchung angelegt.');
      }
      setEditing(null);
      await onSaved();
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={editing.id ? 'Buchung bearbeiten' : 'Neue Buchung'} onClose={() => setEditing(null)}>
      <form onSubmit={save} className="space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="block">
            <span className="label">Datum (Zahlung)</span>
            <input
              type="date"
              className="input"
              value={editing.datum}
              onChange={(e) => setEditing({ ...editing, datum: e.target.value })}
            />
          </label>
          <div className="block">
            <span className="label">Kategorie</span>
            <Dropdown
              value={editing.kategorie_id}
              onChange={(v) => setEditing({ ...editing, kategorie_id: String(v) })}
              options={options}
              placeholder="Kategorie wählen"
            />
          </div>
        </div>

        {isKm ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className="label">Kilometer</span>
              <input
                className="input"
                inputMode="decimal"
                value={editing.km}
                onChange={(e) => setEditing({ ...editing, km: e.target.value })}
                placeholder="z. B. 120"
                autoFocus
              />
              <span className="block text-xs text-ink/60 mt-1">× 0,30 €/km</span>
            </label>
            <div className="block">
              <span className="label">Betrag (berechnet)</span>
              <div className="input bg-ink/5 tabular-nums">
                {computedKmBetrag !== null ? formatEuro(computedKmBetrag) : '—'}
              </div>
            </div>
          </div>
        ) : (
          <label className="block">
            <span className="label">Betrag brutto (€)</span>
            <input
              className="input tabular-nums"
              inputMode="decimal"
              value={editing.betragInput}
              onChange={(e) => setEditing({ ...editing, betragInput: e.target.value })}
              placeholder="0,00"
            />
          </label>
        )}

        {isGwg && (
          <div className="rounded-lg bg-mint-soft/15 border-l-4 border-mint-soft p-3 text-sm text-ink/80">
            GWG-Grenze ist <strong>netto</strong>: 800 € netto ≈ 952 € brutto bei 19 %. Liegt der
            Kaufpreis darüber, gehört das Gut in die AfA-Erfassung statt hierher.
          </div>
        )}
        {isBewirtung && (
          <div className="rounded-lg bg-mint-soft/15 border-l-4 border-mint-soft p-3 text-sm text-ink/80">
            Du erfasst <strong>100 %</strong> des Belegs. Der Export rechnet automatisch 70 % in
            Zeile 63.
          </div>
        )}

        <label className="block">
          <span className="label">Beschreibung {needsBeleg ? '' : '(optional)'}</span>
          <input
            className="input"
            value={editing.beschreibung}
            onChange={(e) => setEditing({ ...editing, beschreibung: e.target.value })}
            placeholder={isKm ? 'Wird sonst automatisch gefüllt' : 'z. B. Rechnung Apple Developer'}
          />
        </label>

        {needsBeleg && (
          <label className="block">
            <span className="label">Beleg-Details (Pflicht)</span>
            <textarea
              className="input min-h-[80px]"
              value={editing.beleg_details}
              onChange={(e) => setEditing({ ...editing, beleg_details: e.target.value })}
              placeholder={BELEG_PLACEHOLDER[selKat?.key] || 'Pflichtangaben am Beleg dokumentieren.'}
            />
          </label>
        )}

        {editing.id ? (
          <div className="pt-2 border-t border-ink/10">
            <BelegeSection buchungId={editing.id} onChange={onSaved} />
          </div>
        ) : (
          <div className="rounded-lg bg-mint-soft/10 p-3 text-sm text-ink/60">
            Belege (PDF/Foto) kannst du nach dem Speichern anhängen.
          </div>
        )}

        <div className="flex flex-col-reverse sm:flex-row sm:justify-end gap-2 pt-2">
          <button type="button" className="btn-ghost" onClick={() => setEditing(null)}>
            {editing.id ? 'Schließen' : 'Abbrechen'}
          </button>
          <button type="submit" className="btn-primary" disabled={busy}>
            Speichern
          </button>
        </div>
      </form>
    </Modal>
  );
}
